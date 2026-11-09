const tabs = document.querySelector('[data-l2c-tabs]');
if (tabs) {
  const botones = Array.from(tabs.querySelectorAll('[role="tab"]'));
  const texto = document.querySelector('[data-l2c-tab-texto]');
  const elegir = (b, enfocar) => {
    botones.forEach((x) => {
      const on = x === b;
      x.classList.toggle('on', on);
      x.setAttribute('aria-selected', on ? 'true' : 'false');
      x.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(x.getAttribute('aria-controls'));
      if (panel) panel.hidden = !on;
      if (on && panel && texto) texto.textContent = panel.dataset.texto || '';
    });
    if (enfocar) b.focus();
  };
  botones.forEach((b, i) => {
    b.addEventListener('click', () => elegir(b));
    b.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      e.preventDefault();
      const n = (i + (e.key === 'ArrowDown' ? 1 : -1) + botones.length) % botones.length;
      elegir(botones[n], true);
    });
  });
}

const estado = document.querySelector('[data-l2c-voz-estado]');
const esferas = Array.from(document.querySelectorAll('[data-l2c-voz]'));
const decir = (txt, hablando) => {
  if (!estado) return;
  estado.classList.toggle('hablando', hablando);
  estado.querySelector('span').textContent = txt;
};
esferas.forEach((b) => b.addEventListener('click', () => {
  esferas.forEach((x) => x.classList.toggle('on', x === b));
  const voz = window.speechSynthesis;
  if (!voz || typeof SpeechSynthesisUtterance === 'undefined') {
    decir(b.dataset.l2cVoz, false);
    return;
  }
  voz.cancel();
  const frase = new SpeechSynthesisUtterance(b.dataset.l2cVoz);
  frase.lang = 'es-CL';
  frase.onend = () => {
    b.classList.remove('on');
    decir('Toca una esfera para escucharla.', false);
  };
  decir('Escuchando…', true);
  voz.speak(frase);
}));
