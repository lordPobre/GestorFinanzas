(() => {
  const plegables = Array.from(document.querySelectorAll('details[data-abrir-escritorio]'));
  if (!plegables.length) return;
  const consulta = window.matchMedia ? window.matchMedia('(min-width: 721px)') : null;

  function ajustar() {
    if (!consulta) return;
    plegables.forEach((d) => { if (consulta.matches) d.open = true; });
  }

  plegables.forEach((d) => d.addEventListener('toggle', () => {
    if (d.open) window.dispatchEvent(new Event('resize'));
  }));
  ajustar();
  if (consulta && consulta.addEventListener) consulta.addEventListener('change', ajustar);
})();
