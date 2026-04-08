from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from core.models import Morador, OrdemServico


def setor_required(group_name=None, morador_attr=None, morador_view_attr=None, morador_edit_attr=None):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_superuser:
                return view_func(request, *args, **kwargs)
            if group_name and user.groups.filter(name=group_name).exists():
                return view_func(request, *args, **kwargs)

            morador = get_user_morador(user)
            can_view = False
            can_edit = False
            if morador:
                if morador_attr:
                    can_view = getattr(morador, morador_attr, False)
                    can_edit = can_view
                if morador_view_attr:
                    can_view = can_view or getattr(morador, morador_view_attr, False)
                if morador_edit_attr:
                    can_edit = can_edit or getattr(morador, morador_edit_attr, False)
            else:
                acesso_usuario = getattr(user, 'acesso_usuario', None)
                if acesso_usuario:
                    if morador_attr:
                        can_view = getattr(acesso_usuario, morador_attr, False)
                        can_edit = can_view
                    if morador_view_attr:
                        can_view = can_view or getattr(acesso_usuario, morador_view_attr, False)
                    if morador_edit_attr:
                        can_edit = can_edit or getattr(acesso_usuario, morador_edit_attr, False)

            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                if can_view or can_edit:
                    return view_func(request, *args, **kwargs)
            elif can_edit:
                return view_func(request, *args, **kwargs)

            raise PermissionDenied('Voce nao tem permissao para acessar este modulo.')

        return _wrapped

    return decorator


def can_edit(request, attr_name):
    if request.user.is_superuser:
        return True
    morador = get_user_morador(request.user)
    if morador:
        return bool(getattr(morador, attr_name, False))
    acesso_usuario = getattr(request.user, 'acesso_usuario', None)
    return bool(acesso_usuario and getattr(acesso_usuario, attr_name, False))


def get_user_morador(user):
    try:
        return user.morador
    except Morador.DoesNotExist:
        return None


def organizar_ordens_por_setor(ordens):
    setor_labels = dict(OrdemServico.SETOR_CHOICES)
    ordens_ativas_por_setor = {setor: [] for setor, _ in OrdemServico.SETOR_CHOICES}
    ordens_finalizadas = []

    for ordem in ordens:
        if ordem.status == 'finalizada':
            ordens_finalizadas.append(ordem)
            continue
        ordens_ativas_por_setor.setdefault(ordem.setor, []).append(ordem)

    secoes_setor = [
        {
            'setor': setor,
            'label': setor_labels.get(setor, setor.title()),
            'ordens': ordens_ativas_por_setor.get(setor, []),
        }
        for setor, _ in OrdemServico.SETOR_CHOICES
    ]
    return secoes_setor, ordens_finalizadas
