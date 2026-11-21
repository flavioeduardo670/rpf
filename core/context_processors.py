"""Dados de navegação disponíveis em todos os templates.

- ``secao_atual``: seção da página (define o boneco do cabeçalho e o item ativo
  do menu).
- ``menu_secoes``: itens do menu lateral que o usuário pode acessar.
- ``mapa_secoes``: prefixos de URL → boneco, usado pela animação de troca de
  página (rpf.transicao.js) para mostrar o boneco da página de destino.
"""
from django.templatetags.static import static
from django.urls import reverse

from core.views.common import GRUPO_POR_MODULO, get_user_morador

# (prefixo da URL, variante do boneco, rótulo, nome da rota do menu, módulo de permissão)
# módulo de permissão: None = qualquer usuário logado; 'superuser' = só administradores.
SECOES = [
    ('/financeiro', 'financeiro', 'Financeiro', 'financeiro', 'financeiro'),
    ('/compras', 'compras', 'Compras', 'compras', 'compras'),
    ('/almoxarifado', 'almoxarifado', 'Almoxarifado', 'almoxarifado', 'estoque'),
    ('/os', 'manutencao', 'Ordens de serviço', 'manutencao', 'manutencao'),
    ('/rock', 'rock', 'Rocks', 'rock', 'rock'),
    ('/reunioes', 'reunioes', 'Reuniões', 'reunioes', 'reunioes'),
    ('/calendario', 'calendario', 'Calendário', 'calendario', 'reunioes'),
    ('/moradores', 'moradores', 'Moradores', 'moradores', None),
    ('/perfil', 'perfil', 'Meu perfil', 'perfil', None),
    ('/acessos', 'acessos', 'Acessos', 'gerenciar_acessos', 'superuser'),
    ('/configuracoes', 'configuracoes', 'Configurações', 'configurar_casa', 'superuser'),
]

# Ordem do menu lateral.
ORDEM_MENU = [
    'moradores', 'financeiro', 'compras', 'almoxarifado', 'manutencao',
    'rock', 'reunioes', 'calendario',
]

INICIO = {'variante': 'inicio', 'rotulo': 'Início'}


def imagens_boneco(variante):
    """Arquivos gerados por scripts/boneco/gerar_boneco.py para a seção."""
    base = 'core/boneco/'
    return {
        'acao': static(f'{base}acao-{variante}-preto.svg'),
        'icone_branco': static(f'{base}icone-{variante}-branco.svg'),
        'icone_preto': static(f'{base}icone-{variante}-preto.svg'),
        'corrida': static(f'{base}corrida-{variante}.svg'),
    }


def secao_por_caminho(caminho):
    for prefixo, variante, rotulo, _rota, _modulo in SECOES:
        if caminho == prefixo or caminho.startswith(prefixo + '/'):
            return {'variante': variante, 'rotulo': rotulo}
    return INICIO


def pode_ver_modulo(user, modulo):
    if not user.is_authenticated:
        return False
    if user.is_superuser or modulo is None:
        return True
    if modulo == 'superuser':
        return False
    grupo = GRUPO_POR_MODULO.get(modulo)
    if grupo and user.groups.filter(name=grupo).exists():
        return True
    alvo = get_user_morador(user) or getattr(user, 'acesso_usuario', None)
    if not alvo:
        return False
    return bool(
        getattr(alvo, f'acesso_{modulo}_visualizar', False)
        or getattr(alvo, f'acesso_{modulo}_editar', False)
    )


def navegacao(request):
    secao = secao_por_caminho(request.path)
    user = getattr(request, 'user', None)
    menu = []
    if user is not None and user.is_authenticated:
        por_variante = {s[1]: s for s in SECOES}
        for variante in ORDEM_MENU:
            _prefixo, _v, rotulo, rota, modulo = por_variante[variante]
            if pode_ver_modulo(user, modulo):
                menu.append({
                    'variante': variante,
                    'rotulo': rotulo,
                    'url': reverse(rota),
                    'ativo': secao['variante'] == variante,
                    'imagens': imagens_boneco(variante),
                })
    mapa = {
        'secoes': [
            {'prefixo': prefixo, 'variante': variante, 'rotulo': rotulo,
             'corrida': static(f'core/boneco/corrida-{variante}.svg')}
            for prefixo, variante, rotulo, _rota, _modulo in SECOES
        ],
        'inicio': {'variante': 'inicio', 'rotulo': 'Início', 'corrida': static('core/boneco/corrida-inicio.svg')},
        'chegada': static('core/boneco/porta-abrindo.svg'),
    }
    return {
        'secao_atual': dict(secao, imagens=imagens_boneco(secao['variante'])),
        'menu_secoes': menu,
        'imagens_inicio': imagens_boneco('inicio'),
        'mapa_secoes': mapa,
    }
