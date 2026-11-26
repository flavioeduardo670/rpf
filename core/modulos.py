"""Módulos do ERP e quais estão ligados para cada cliente.

Cada organização liga só o que usa. Um módulo desligado some do menu e da
página inicial, suas páginas respondem 404 e os itens dele saem do
calendário e do perfil.

Chave do módulo = "variante" usada no menu e no boneco (core/context_processors.py).
Textos entre chaves vêm do vocabulário do cliente (core/terminologia.py).
"""
from django.http import Http404

# chave -> (rótulo, descrição, obrigatório)
MODULOS = {
    'moradores': ('{Membros}', 'Cadastro das pessoas, {unidades} e funções.', True),
    'financeiro': ('Financeiro', '{Cobranca}, rateio das contas, boleto PIX e prestação de contas.', False),
    'compras': ('Compras', 'Notas fiscais (inclusive pelo QR Code) e parcelas.', False),
    'almoxarifado': ('Almoxarifado', 'Estoque, locais de armazenamento e consumo de produtos.', False),
    'manutencao': ('Ordens de serviço', 'Pedidos de conserto e materiais usados.', False),
    'rock': ('{Eventos}', '{Eventos} com lotes e venda de ingressos por PIX.', False),
    'reunioes': ('Reuniões', 'Pautas, atas e plano de ação.', False),
    'calendario': ('Calendário', 'Agenda do mês, com os itens dos outros módulos.', False),
}

TODOS = list(MODULOS)
OBRIGATORIOS = {chave for chave, (_r, _d, obrigatorio) in MODULOS.items() if obrigatorio}

# Pacote inicial de cada segmento (a organização pode mudar no Admin).
PADRAO_POR_SEGMENTO = {
    'moradia': TODOS,
    'bar': ['moradores', 'financeiro', 'compras', 'almoxarifado', 'manutencao', 'rock', 'calendario'],
    'mercado': ['moradores', 'financeiro', 'compras', 'almoxarifado', 'manutencao', 'calendario'],
    'agro': ['moradores', 'financeiro', 'compras', 'almoxarifado', 'manutencao', 'calendario'],
    'saude': ['moradores', 'financeiro', 'compras', 'almoxarifado', 'manutencao', 'reunioes', 'calendario'],
    'outro': ['moradores', 'financeiro', 'compras', 'calendario'],
}

# Endereços que continuam abertos mesmo com o módulo desligado: notificações
# do Mercado Pago chegam por eles e não podem ser perdidas.
CAMINHOS_LIVRES = ('/rock/pix/webhook/', '/financeiro/pix/webhook/')


def modulos_do_segmento(segmento):
    return list(PADRAO_POR_SEGMENTO.get(segmento) or PADRAO_POR_SEGMENTO['outro'])


def resolver_ativos(segmento, escolhidos):
    """Módulos ligados: os escolhidos (ou o pacote do segmento) + os obrigatórios."""
    base = [m for m in (escolhidos or []) if m in MODULOS] or modulos_do_segmento(segmento)
    return frozenset(base) | OBRIGATORIOS


def opcoes_para_formulario(termos):
    """(chave, 'Rótulo — descrição') para as caixas de seleção do Admin."""
    return [
        (chave, f'{rotulo.format_map(termos)} — {descricao.format_map(termos)}' + (' (sempre ligado)' if obrigatorio else ''))
        for chave, (rotulo, descricao, obrigatorio) in MODULOS.items()
    ]


def modulo_do_caminho(caminho):
    """Módulo dono de uma URL (pelo prefixo do menu), ou None."""
    from core.context_processors import SECOES

    for prefixo, variante, _rotulo, _rota, _permissao in SECOES:
        if variante in MODULOS and (caminho == prefixo or caminho.startswith(prefixo + '/')):
            return variante
    return None


class ModuloAtivoMiddleware:
    """Responde 404 para páginas de módulos que o cliente não ligou."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        caminho = request.path
        if not caminho.startswith(CAMINHOS_LIVRES):
            modulo = modulo_do_caminho(caminho)
            if modulo:
                from core.models import Organizacao

                if modulo not in Organizacao.atual().modulos_ativos:
                    raise Http404('Módulo não disponível para esta organização.')
        return self.get_response(request)
