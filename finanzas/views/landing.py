from django.shortcuts import redirect, render

from .panel import dashboard


def inicio(request):
    if request.user.is_authenticated:
        return dashboard(request)
    if request.GET.get('fuente') == 'pwa':
        return redirect('login')
    return render(request, 'finanzas/landing.html')
