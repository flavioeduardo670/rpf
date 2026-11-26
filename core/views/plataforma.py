"""Telas da plataforma (não pertencem a nenhum módulo)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from core.organizacao_atual import CHAVE_SESSAO, organizacoes_do_usuario


@login_required
@require_POST
def trocar_organizacao(request):
    """Troca a organização em uso, entre as que o usuário participa."""
    org = organizacoes_do_usuario(request.user).filter(pk=request.POST.get('organizacao')).first()
    if org is None:
        messages.error(request, 'Você não participa dessa organização.')
    else:
        request.session[CHAVE_SESSAO] = org.pk
        messages.success(request, f'Agora você está em {org.nome}.')
    return redirect('home')
