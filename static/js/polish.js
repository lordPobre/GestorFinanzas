/* ============================================================
   FinApp · Capa de pulido — JavaScript
   Reemplaza el confirm() nativo del navegador por un modal
   propio con la estética de la app, sin romper los formularios.
   ============================================================ */

(function () {
    'use strict';

    // ----- Inyectar el modal en el DOM una sola vez -----
    function ensureModal() {
        if (document.getElementById('confirm-overlay')) return;
        const overlay = document.createElement('div');
        overlay.id = 'confirm-overlay';
        overlay.innerHTML = `
            <div id="confirm-box">
                <div id="confirm-icon"><i class="fas fa-trash"></i></div>
                <div id="confirm-title">¿Estás seguro?</div>
                <div id="confirm-msg">Esta acción no se puede deshacer.</div>
                <div id="confirm-actions">
                    <button class="confirm-btn confirm-cancel" type="button">Cancelar</button>
                    <button class="confirm-btn confirm-delete" type="button">Eliminar</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);

        // Cerrar al hacer clic fuera del cuadro
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) cerrar();
        });
        // Cerrar con Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') cerrar();
        });
    }

    let onConfirmCallback = null;

    function abrir({ titulo, mensaje, textoBoton, callback }) {
        ensureModal();
        document.getElementById('confirm-title').textContent = titulo || '¿Estás seguro?';
        document.getElementById('confirm-msg').textContent = mensaje || 'Esta acción no se puede deshacer.';
        document.querySelector('.confirm-delete').textContent = textoBoton || 'Eliminar';
        onConfirmCallback = callback;

        const overlay = document.getElementById('confirm-overlay');
        overlay.classList.add('open');

        // Re-vincular botones (se recrean textos, no listeners)
        const cancelBtn = overlay.querySelector('.confirm-cancel');
        const deleteBtn = overlay.querySelector('.confirm-delete');
        cancelBtn.onclick = cerrar;
        deleteBtn.onclick = () => {
            // Guardar el callback ANTES de cerrar (cerrar lo pone en null)
            const cb = onConfirmCallback;
            cerrar();
            if (typeof cb === 'function') cb();
        };
    }

    function cerrar() {
        const overlay = document.getElementById('confirm-overlay');
        if (overlay) overlay.classList.remove('open');
        onConfirmCallback = null;
    }

    // ----- API pública -----
    window.finConfirm = abrir;

    // ============================================================
    //  Interceptar formularios de eliminación automáticamente
    //  Cualquier <form> con data-confirm usa el modal bonito.
    // ============================================================
    document.addEventListener('submit', function (e) {
        const form = e.target;
        const mensaje = form.getAttribute('data-confirm');
        if (!mensaje) return;              // no tiene data-confirm → flujo normal
        if (form.dataset.confirmed) {      // ya confirmado → dejar pasar
            form.dataset.confirmed = '';
            return;
        }
        e.preventDefault();
        abrir({
            titulo: form.getAttribute('data-confirm-title') || '¿Eliminar?',
            mensaje: mensaje,
            textoBoton: form.getAttribute('data-confirm-btn') || 'Eliminar',
            callback: () => {
                form.dataset.confirmed = '1';
                form.submit();
            }
        });
    }, true);

    // ============================================================
    //  Marcar mensajes/toasts existentes con animación de entrada
    // ============================================================
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-toast], .system-toast').forEach(el => {
            el.classList.add('toast-enter');
        });
    });

})();
