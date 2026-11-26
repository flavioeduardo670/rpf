"""Dados de navegação disponíveis em todos os templates.

- ``secao_atual``: seção da página (define o boneco do cabeçalho e o item ativo
  do menu).
- ``menu_secoes``: itens do menu do topo que o usuário pode acessar.
- ``mapa_secoes``: prefixos de URL → boneco, usado pela animação de troca de
  página (rpf.transicao.js) para mostrar o boneco da página de destino.
- ``organizacao`` / ``produto_nome``: o cliente desta instalação (nome, marca)
  e o nome do ERP, no lugar dos textos fixos da República Portão dos Fundos.
"""
from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from core.models import Organizacao
from core.modulos import MODULOS
from core.views.common import GRUPO_POR_MODULO, get_user_morador


def marca(request):
    from core.organizacao_atual import organizacoes_do_usuario

    organizacao = Organizacao.atual()
    user = getattr(request, 'user', None)
    return {
        # Só aparece o seletor de organização para quem participa de mais de uma.
        'organizacoes_do_usuario': list(organizacoes_do_usuario(user)) if user is not None else [],
        'organizacao': organizacao,
        'produto_nome': settings.PRODUTO_NOME,
        'termos': organizacao.vocabulario,
        'modulos_ativos': organizacao.modulos_ativos,
    }

# (prefixo da URL, variante do boneco, rótulo, nome da rota do menu, módulo de permissão)
# módulo de permissão: None = qualquer usuário logado; 'superuser' = só administradores.
# Rótulos entre chaves vêm do vocabulário do cliente (core/terminologia.py).
SECOES = [
    ('/financeiro', 'financeiro', 'Financeiro', 'financeiro', 'financeiro'),
    ('/compras', 'compras', 'Compras', 'compras', 'compras'),
    ('/almoxarifado', 'almoxarifado', 'Almoxarifado', 'almoxarifado', 'estoque'),
    ('/os', 'manutencao', 'Ordens de serviço', 'manutencao', 'manutencao'),
    ('/rock', 'rock', '{Eventos}', 'rock', 'rock'),
    ('/reunioes', 'reunioes', 'Reuniões', 'reunioes', 'reunioes'),
    ('/calendario', 'calendario', 'Calendário', 'calendario', 'reunioes'),
    ('/moradores', 'moradores', '{Membros}', 'moradores', None),
    ('/perfil', 'perfil', 'Meu perfil', 'perfil', None),
    ('/acessos', 'acessos', 'Acessos', 'gerenciar_acessos', 'superuser'),
    ('/configuracoes', 'configuracoes', 'Configurações', 'configurar_casa', 'superuser'),
]

# Ordem do menu do topo.
ORDEM_MENU = [
    'moradores', 'financeiro', 'compras', 'almoxarifado', 'manutencao',
    'rock', 'reunioes', 'calendario',
]

INICIO = {'variante': 'inicio', 'rotulo': 'Início'}

# Animações em vídeo do boneco (loop-<seção>.webp, boneco preto com fundo
# transparente): variante -> (largura, altura) do arquivo. Seções sem loop
# continuam com a ação em SVG (acao-<seção>-preto.svg).
LOOPS = {
    'inicio': (399, 300),
    'moradores': (452, 300),
    'financeiro': (237, 300),
    'compras': (366, 300),
    'almoxarifado': (298, 300),
    'manutencao': (324, 300),
    'rock': (518, 300),
    'reunioes': (303, 300),
    'calendario': (515, 300),
    'perfil': (196, 300),
}


def imagens_boneco(variante):
    """Desenhos da seção: SVGs de scripts/boneco/gerar_boneco.py e o loop em vídeo."""
    base = 'core/boneco/'
    loop = None
    if variante in LOOPS:
        largura, altura = LOOPS[variante]
        loop = {'url': static(f'{base}loop-{variante}.webp'), 'largura': largura, 'altura': altura}
    return {
        'loop': loop,
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
    organizacao = Organizacao.atual()
    termos = organizacao.vocabulario
    ativos = organizacao.modulos_ativos
    secao = secao_por_caminho(request.path)
    secao = dict(secao, rotulo=secao['rotulo'].format_map(termos))
    user = getattr(request, 'user', None)
    menu = []
    if user is not None and user.is_authenticated:
        por_variante = {s[1]: s for s in SECOES}
        for variante in ORDEM_MENU:
            _prefixo, _v, rotulo, rota, modulo = por_variante[variante]
            if variante in ativos and pode_ver_modulo(user, modulo):
                menu.append({
                    'variante': variante,
                    'rotulo': rotulo.format_map(termos),
                    'url': reverse(rota),
                    'ativo': secao['variante'] == variante,
                    'imagens': imagens_boneco(variante),
                })
    mapa = {
        'secoes': [
            {'prefixo': prefixo, 'variante': variante, 'rotulo': rotulo.format_map(termos),
             'corrida': static(f'core/boneco/corrida-{variante}.svg')}
            for prefixo, variante, rotulo, _rota, _modulo in SECOES
            if variante not in MODULOS or variante in ativos
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
