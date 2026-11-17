/* Adapt document chrome once; the existing renderer remains the data owner. */
(() => {
  const title = document.querySelector('#tableTitle');
  const bar = document.querySelector('.topbar');
  if (title && bar) {
    const heading = document.createElement('div');
    heading.className = 'studio-document-title';
    heading.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3z"/><path d="M3 10h18"/></svg>';
    heading.append(title);
    bar.insertBefore(heading, bar.querySelector('.top-actions'));
    const name = document.querySelector('.sidebar-head strong');
    if (name) name.textContent = '内容研究';
  }
  // Keep dialogs' native Esc/focus behavior; focus returns to their opener.
  let opener = null;
  document.addEventListener('click', event => { if (!event.target.closest('dialog')) opener = event.target.closest('button,a'); }, true);
  document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('close', () => {
    if (opener && opener.isConnected) opener.focus({preventScroll:true});
  }));
})();
