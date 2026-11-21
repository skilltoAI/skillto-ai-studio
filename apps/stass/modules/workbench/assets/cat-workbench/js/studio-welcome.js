const agreement = document.getElementById('agreement');
const agree = document.getElementById('agreeBtn');
agreement.onchange = () => { agree.disabled = !agreement.checked; };
agree.onclick = async () => {
  if (!agreement.checked) return;
  await chrome.storage.local.set({studioAccepted: true, studioAcceptedAt: new Date().toISOString()});
  document.getElementById('welcomeStatus').textContent = '已就绪。回到视频页，点击工具栏的工作台图标即可开始。';
  agree.textContent = '已就绪，开始发现视频 ✓'; agree.disabled = true;
};
