/* Adapt document chrome once; the existing renderer remains the data owner. */
(() => {
  // Keep dialogs' native Esc/focus behavior; focus returns to their opener.
  let opener = null;
  document.addEventListener('click', event => { if (!event.target.closest('dialog')) opener = event.target.closest('button,a'); }, true);
  document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('close', () => {
    if (opener && opener.isConnected) opener.focus({preventScroll:true});
  }));
})();
