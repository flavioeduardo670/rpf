from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms import modelformset_factory
from django.shortcuts import redirect, render

from core.forms import AcessoMoradorForm, AcessoUsuarioForm
from core.models import AcessoUsuario, Morador

AcessoMoradorFormSet = modelformset_factory(Morador, form=AcessoMoradorForm, extra=0)
AcessoUsuarioFormSet = modelformset_factory(AcessoUsuario, form=AcessoUsuarioForm, extra=0)


@login_required
def gerenciar_acessos(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Voce nao tem permissao para acessar este modulo.')

    User = get_user_model()
    moradores_qs = Morador.objects.order_by('ordem_hierarquia', 'nome')
    usuarios_sem_morador = User.objects.filter(morador__isnull=True, is_superuser=False).order_by('username')
    for usuario in usuarios_sem_morador:
        AcessoUsuario.objects.get_or_create(user=usuario)
    acessos_usuarios_qs = AcessoUsuario.objects.select_related('user').filter(user__in=usuarios_sem_morador).order_by('user__username')
    moradores_sem_usuario = Morador.objects.filter(user__isnull=True).order_by('ordem_hierarquia', 'nome')

    if request.method == 'POST':
        formset = AcessoMoradorFormSet(request.POST, queryset=moradores_qs)
        usuario_formset = AcessoUsuarioFormSet(request.POST, queryset=acessos_usuarios_qs, prefix='usuarios')
        if formset.is_valid() and usuario_formset.is_valid():
            formset.save(); usuario_formset.save()
            moradores_livres = {m.id: m for m in Morador.objects.filter(user__isnull=True)}
            for acesso_usuario in acessos_usuarios_qs:
                morador_id = request.POST.get(f'vinculo_morador_{acesso_usuario.user_id}')
                if morador_id and str(morador_id).isdigit() and int(morador_id) in moradores_livres:
                    morador = moradores_livres[int(morador_id)]
                    morador.user = acesso_usuario.user
                    morador.save(update_fields=['user'])
                    moradores_livres.pop(int(morador_id), None)
            messages.success(request, 'Acessos atualizados com sucesso.')
            return redirect('gerenciar_acessos')
        messages.error(request, 'Nao foi possivel salvar os acessos. Revise os campos destacados.')
    else:
        formset = AcessoMoradorFormSet(queryset=moradores_qs)
        usuario_formset = AcessoUsuarioFormSet(queryset=acessos_usuarios_qs, prefix='usuarios')

    return render(request, 'core/gerenciar_acessos.html', {'formset': formset, 'usuario_formset': usuario_formset, 'moradores_sem_usuario': moradores_sem_usuario})
