#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');

function readStatus(root) {
  const location = path.join(root, 'config', 'installation.json');
  if (!fs.existsSync(location)) return {installed: false, root};
  const state = JSON.parse(fs.readFileSync(location, 'utf8'));
  if (state.format !== 1 || typeof state.instanceId !== 'string') throw new Error('Unsupported installation state');
  // Never print client tokens or arbitrary configuration fields.
  return {installed: true, root, instanceId: state.instanceId, url: state.url,
    activeVersion: state.activeVersion, hosts: Object.keys(state.hosts || {})};
}

async function doctor(root) {
  const state = readStatus(root);
  const issues = [];
  if (!state.installed) issues.push('Shared program is not installed');
  else if (!state.activeVersion) issues.push('Shared state exists but no program version is activated');
  else {
    const endpoint = new URL(state.url);
    if (endpoint.protocol !== 'http:' || endpoint.hostname !== '127.0.0.1' || endpoint.pathname !== '/STASS/' || endpoint.username || endpoint.password)
      throw new Error('Invalid local instance endpoint');
    try {
      const response = await fetch(new URL('health', endpoint), {signal: AbortSignal.timeout(3000), redirect: 'error'});
      if (!response.ok) throw new Error('Health request failed');
      const health = await response.json();
      if (health.service !== 'STASS' || health.instanceId !== state.instanceId) issues.push('Service identity mismatch');
      if (health.status?.includes('pending')) issues.push('Program integration is incomplete');
    } catch { issues.push('Shared service health could not be verified'); }
  }
  return {...state, ready: issues.length === 0, issues};
}

async function main(args) {
  if (!args.length || args[0] === '--help') {
    console.log('STASS private Windows manager\nCommands: status, doctor, start, stop\nInstallation and update distribution are under development; no release is available.');
    return 0;
  }
  if (process.platform !== 'win32') throw new Error('Shared program management currently requires Windows');
  const root = path.join(process.env.LOCALAPPDATA, 'Skillto.ai', 'Studio');
  if (args.length !== 1) throw new Error('Unexpected arguments');
  if (args[0] === 'status') { console.log(JSON.stringify(readStatus(root), null, 2)); return 0; }
  if (args[0] === 'doctor') { const result = await doctor(root); console.log(JSON.stringify(result, null, 2)); return result.ready ? 0 : 1; }
  if (args[0] === 'start' || args[0] === 'stop') {
    const state = JSON.parse(fs.readFileSync(path.join(root, 'config/installation.json'), 'utf8'));
    if (!state.program?.python || !state.program?.directory) throw new Error('No program registered');
    const result = spawnSync(state.program.python, [path.join(state.program.directory, 'runtime_control.py'), args[0], '--root', root], {stdio:'inherit', windowsHide:true, shell:false});
    if (result.error) throw new Error('Could not launch the registered program manager');
    return result.status ?? 1;
  }
  throw new Error('This command is not implemented yet; no program or host configuration was changed');
}

module.exports = {readStatus, doctor};
if (require.main === module) main(process.argv.slice(2)).then(code => {process.exitCode = code;}).catch(error => {console.error(error.message); process.exitCode = 1;});
