document.querySelectorAll('[data-mes-elegir]').forEach(function (campo) {
  campo.addEventListener('change', function () {
    if (campo.form) campo.form.submit();
  });
});
