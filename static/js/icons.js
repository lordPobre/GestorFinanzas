/* ============================================================
   FinApp · Iconos modernos (SVG inline, sin CDN)
   Reemplaza los <i class="fas fa-*"> por SVG de línea modernos.
   No depende de ningún CDN externo — garantiza que siempre carguen.
   ============================================================ */

(function () {
    'use strict';

    // Cada ícono es el contenido interno de un <svg viewBox="0 0 24 24">
    const P = {
        'fa-lightbulb':   '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.5.4.8 1 .9 1.6h6.2c.1-.6.4-1.2.9-1.6A7 7 0 0 0 12 2z"/>',
        'fa-info-circle': '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
        'fa-smile':       '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><path d="M9 9h.01"/><path d="M15 9h.01"/>',
        'fa-coins':       '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="M16.71 13.88l.7.71-2.82 2.82"/>',
        'fa-money':       '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
        'fa-briefcase':   '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
        'fa-laptop':      '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M2 20h20"/>',
        'fa-store':       '<path d="M2 7l1-4h18l1 4"/><path d="M4 7v13a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V7"/><path d="M9 21v-6h6v6"/>',
        'fa-box':         '<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/>',
        'fa-gift':        '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/><path d="M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8s1-5 4.5-5a2.5 2.5 0 0 1 0 5"/>',
        'fa-exchange':    '<path d="M17 3l4 4-4 4"/><path d="M21 7H3"/><path d="M7 21l-4-4 4-4"/><path d="M3 17h18"/>',
        'fa-sparkles':    '<path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3z"/>',
        'fa-tag':         '<path d="M12 2H2v10l9.29 9.29a1 1 0 0 0 1.42 0l8.58-8.58a1 1 0 0 0 0-1.42z"/><path d="M7 7h.01"/>',
        'fa-calendar':    '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
        'fa-shopping-cart':'<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
        'fa-car':         '<path d="M5 17H3v-6l2-5h14l2 5v6h-2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M9 17h6"/>',
        'fa-pills':       '<path d="M10.5 20.5a4.95 4.95 0 0 1-7-7l7-7a4.95 4.95 0 0 1 7 7z"/><path d="M8.5 8.5l7 7"/>',
        'fa-film':        '<rect x="2" y="2" width="20" height="20" rx="2"/><path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5"/>',
        'fa-bolt':        '<path d="M13 2L3 14h9l-1 8 10-12h-9z"/>',
        'fa-party':       '<path d="M5.8 11.3L2 22l10.7-3.79"/><path d="M4 3h.01M22 8h.01M15 2h.01M22 20h.01"/><path d="M22 2l-2.24.75a2.9 2.9 0 0 0-1.96 3.12c.1.86-.57 1.63-1.45 1.63h-.38c-.86 0-1.6.6-1.76 1.44L14 10"/><path d="M11.5 10.5c1.5 1.5 4 2 4 2"/>',
        'fa-arrow-down':  '<path d="M12 5v14"/><path d="M19 12l-7 7-7-7"/>',
        'fa-arrow-up':    '<path d="M12 19V5"/><path d="M5 12l7-7 7 7"/>',
        'fa-arrow-left':  '<path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/>',
        'fa-arrow-right': '<path d="M5 12h14"/><path d="M12 5l7 7-7 7"/>',
        'fa-chart-line':  '<path d="M3 3v18h18"/><path d="M7 14l3-3 4 4 5-6"/>',
        'fa-chart-pie':   '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
        'fa-check':       '<path d="M20 6L9 17l-5-5"/>',
        'fa-check-circle':'<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>',
        'fa-chevron-left':'<path d="M15 18l-6-6 6-6"/>',
        'fa-chevron-right':'<path d="M9 18l6-6-6-6"/>',
        'fa-circle':      '<circle cx="12" cy="12" r="10"/>',
        'fa-credit-card': '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
        'fa-download':    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
        'fa-exclamation-triangle':'<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
        'fa-home':        '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
        'fa-key':         '<circle cx="7.5" cy="15.5" r="5.5"/><path d="M11.5 11.5L21 2"/><path d="M18 5l3 3"/><path d="M15 8l3 3"/>',
        'fa-lock':        '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
        'fa-map-marker-alt':'<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
        'fa-minus':       '<path d="M5 12h14"/>',
        'fa-minus-circle':'<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
        'fa-plus':        '<path d="M12 5v14"/><path d="M5 12h14"/>',
        'fa-plus-circle': '<circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="M8 12h8"/>',
        'fa-pen':         '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
        'fa-piggy-bank':  '<path d="M19 5c-1.5 0-2.8 1.4-3 2-3.5-1.5-11-.3-11 5 0 1.8 0 3 2 4.5V20h4v-2h3v2h4v-4c1-.5 1.7-1 2-2h2v-4h-2c0-1-.5-1.5-1-2z"/><circle cx="16" cy="11" r="1"/>',
        'fa-receipt':     '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1z"/><path d="M8 7h8"/><path d="M8 11h8"/><path d="M8 15h5"/>',
        'fa-rocket':      '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
        'fa-save':        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/>',
        'fa-sign-out-alt':'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
        'fa-sliders-h':   '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
        'fa-times':       '<path d="M18 6L6 18"/><path d="M6 6l12 12"/>',
        'fa-times-circle':'<circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6"/><path d="M9 9l6 6"/>',
        'fa-trash':       '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
        'fa-undo':        '<path d="M3 7v6h6"/><path d="M3 13a9 9 0 1 0 3-7.7L3 8"/>',
        'fa-user':        '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
        'fa-user-circle': '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="10" r="3"/><path d="M7 20.66a8 8 0 0 1 10 0"/>',
        'fa-wallet':      '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5"/><path d="M16 12h.01"/>',
        'fa-spinner':     '<path d="M12 2v4"/><path d="M12 18v4"/><path d="M4.93 4.93l2.83 2.83"/><path d="M16.24 16.24l2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="M4.93 19.07l2.83-2.83"/><path d="M16.24 7.76l2.83-2.83"/>'
    };

    const SVG_NS = 'http://www.w3.org/2000/svg';

    function crearSVG(inner, size, color, girando) {
        const svg = document.createElementNS(SVG_NS, 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('width', size);
        svg.setAttribute('height', size);
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', color);
        svg.setAttribute('stroke-width', '2');
        svg.setAttribute('stroke-linecap', 'round');
        svg.setAttribute('stroke-linejoin', 'round');
        svg.style.display = 'inline-block';
        svg.style.verticalAlign = 'middle';
        svg.style.flexShrink = '0';
        if (girando) svg.style.animation = 'iconspin 0.8s linear infinite';
        svg.innerHTML = inner;
        return svg;
    }

    function reemplazar(root) {
        const iconos = (root || document).querySelectorAll('i[class*="fa-"]');
        iconos.forEach(el => {
            let inner = null;
            for (const cls of el.classList) {
                if (P[cls]) { inner = P[cls]; break; }
            }
            if (!inner) return;

            const cs = getComputedStyle(el);
            const size = parseFloat(cs.fontSize) || 16;
            const color = cs.color || 'currentColor';
            const girando = el.classList.contains('fa-spin');

            const svg = crearSVG(inner, size, color, girando);
            // Preservar márgenes inline del <i> original
            if (el.style.marginRight) svg.style.marginRight = el.style.marginRight;
            if (el.style.marginLeft)  svg.style.marginLeft  = el.style.marginLeft;
            el.replaceWith(svg);
        });
    }

    // Animación de giro
    const style = document.createElement('style');
    style.textContent = '@keyframes iconspin { to { transform: rotate(360deg); } }';
    document.head.appendChild(style);

    function init() { reemplazar(document); }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Re-aplicar tras insertar HTML dinámico (celebración, toasts)
    window.aplicarIconos = () => reemplazar(document);

})();
