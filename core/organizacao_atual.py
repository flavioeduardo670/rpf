"""Qual organização (cliente) está em uso em cada acesso.

O usuário logado pode participar de várias organizações (modelo Vinculo).
O middleware escolhe uma por requisição: a que ele trocou por último (guardada
na sessão) ou a primeira dele. Superusuários (equipe da plataforma) podem abrir
qualquer organização ativa.

``Organizacao.atual()`` lê daqui; o valor vale só durante a requisição
(contextvars), então não vaza entre acessos de usuários diferentes.
"""
from contextvars import ContextVar

from django.core.exceptions import PermissionDenied

CHAVE_SESSAO = 'organizacao_id'

_organizacao: ContextVar = ContextVar('organizacao_atual', default=None)


def organizacao_da_requisicao():
    return _organizacao.get()


def definir_organizacao(org):
    """Para testes e rotinas que agem em nome de uma organização. Devolve o token para desfazer."""
    return _organizacao.set(org)


def desfazer(token):
    _organizacao.reset(token)


def organizacao_da_instalacao():
    """O cliente original da instalação (a primeira organização ativa).

    Dono das credenciais que ainda ficam nas variáveis do servidor (certificado
    da NF-e, caixa de email das notas).
    """
    from core.models import Organizacao

    return Organizacao.objects.filter(ativa=True).order_by('id').first()


class na_organizacao:
    """``with na_organizacao(org):`` age em nome de uma organização (webhooks, rotinas, recibos)."""

    def __init__(self, org):
        self.org = org

    def __enter__(self):
        self._token = _organizacao.set(self.org)
        return self.org

    def __exit__(self, *exc):
        _organizacao.reset(self._token)
        return False


def organizacoes_do_usuario(user):
    from core.models import Organizacao

    if not getattr(user, 'is_authenticated', False):
        return Organizacao.objects.none()
    ativas = Organizacao.objects.filter(ativa=True).order_by('id')
    if user.is_superuser:
        return ativas
    return ativas.filter(vinculos__usuario=user).distinct()


def escolher_organizacao(request):
    """A organização deste acesso, ou None (sem login / sem vínculo)."""
    disponiveis = organizacoes_do_usuario(request.user)
    escolhida = request.session.get(CHAVE_SESSAO) if hasattr(request, 'session') else None
    if escolhida:
        org = disponiveis.filter(pk=escolhida).first()
        if org:
            return org
    return disponiveis.first()


class OrganizacaoAtualMiddleware:
    """Define a organização do acesso logo depois da autenticação."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        org = escolher_organizacao(request)
        user = request.user
        if (org is None and user.is_authenticated and not user.is_superuser
                and request.path != '/logout/' and _ha_varias_organizacoes()):
            # Logado, mas sem vínculo com nenhuma organização: não pode ver dados de ninguém.
            raise PermissionDenied('Seu usuário não está vinculado a nenhuma organização. Fale com o administrador.')
        request.organizacao = org
        token = _organizacao.set(org)
        try:
            return self.get_response(request)
        finally:
            _organizacao.reset(token)


def instalar_filtro_nos_formularios():
    """Listas de seleção de formulário (ModelChoiceField) só com dados da organização em uso.

    O Django monta essas listas quando o formulário é definido (ao iniciar o
    sistema, fora de qualquer acesso), então o filtro do gerenciador não pega.
    Cada formulário criado copia seus campos (__deepcopy__): é aí que filtramos.
    """
    from django.forms import models as form_models

    from core.models import ModeloDaOrganizacao

    original = form_models.ModelChoiceField.__deepcopy__
    if getattr(original, '_filtra_organizacao', False):
        return

    def deepcopy_com_filtro(self, memo):
        copia = original(self, memo)
        queryset = copia.queryset
        org = organizacao_da_requisicao()
        if org is not None and queryset is not None and issubclass(queryset.model, ModeloDaOrganizacao):
            copia.queryset = queryset.filter(organizacao=org)
        return copia

    deepcopy_com_filtro._filtra_organizacao = True
    form_models.ModelChoiceField.__deepcopy__ = deepcopy_com_filtro


def _ha_varias_organizacoes():
    from core.models import Organizacao

    return Organizacao.objects.filter(ativa=True).count() > 1
