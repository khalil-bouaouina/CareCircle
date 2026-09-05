function renderQR(elementId, text) {
  const element = document.getElementById(elementId);
  if (element && window.QRCode) {
    element.replaceChildren();
    new QRCode(element, text);
  }
}

function copyLink(elementId) {
  const element = document.getElementById(elementId);
  if (!element || !navigator.clipboard) return;
  navigator.clipboard.writeText(element.textContent.trim()).then(() => {
    const button = document.querySelector('[data-copy-for="' + elementId + '"]');
    if (!button) return;
    const original = button.textContent;
    button.textContent = 'Copié';
    setTimeout(() => { button.textContent = original; }, 2000);
  });
}
