import json
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from core.models import (
    ConsumoEstoque,
    EventoCalendario,
    Morador,
    NotaFiscal,
    OrdemServico,
    Produto,
    RockEvento,
)


PAGE_META = {
    'home': {'titulo': 'Home'},
    'calendario': {'titulo': 'Calendário'},
    'perfil': {'titulo': 'Perfil'},
    'moradores': {'titulo': 'Moradores'},
    'financeiro': {'titulo': 'Financeiro'},
    'compras': {'titulo': 'Compras'},
    'rock': {'titulo': 'Rock'},
    'almoxarifado': {'titulo': 'Almoxarifado'},
    'manutencao': {'titulo': 'Manutenção'},
}


ENDPOINTS = {
    'home': '/api/paginas/home/relatorio/',
    'calendario': '/api/paginas/calendario/relatorio/',
    'perfil': '/api/paginas/perfil/relatorio/',
    'moradores': '/api/paginas/moradores/relatorio/',
    'financeiro': '/api/paginas/financeiro/relatorio/',
    'compras': '/api/paginas/compras/relatorio/',
    'rock': '/api/paginas/rock/relatorio/',
    'almoxarifado': '/api/paginas/almoxarifado/relatorio/',
    'manutencao': '/api/paginas/manutencao/relatorio/',
}


def _check_api_key(request):
    configured_key = getattr(settings, 'ERP_API_KEY', '')
    if not configured_key:
        return JsonResponse({'detail': 'ERP_API_KEY não configurada no servidor.'}, status=503)

    provided_key = request.headers.get('X-API-Key')
    if provided_key != configured_key:
        return JsonResponse({'detail': 'Não autorizado.'}, status=401)
    return None


def _json(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})


def _fmt_money(value):
    value = Decimal(value or 0)
    return f'R$ {value:.2f}'


def _fmt_date(value):
    if not value:
        return '-'
    return value.strftime('%d/%m/%Y')


def _to_lines(page_key, morador):
    if page_key == 'home':
        moradores_ativos = Morador.objects.filter(ativo=True).count()
        notas_pendentes = NotaFiscal.objects.filter(status='pendente').count()
        os_abertas = OrdemServico.objects.filter(status__in=['aberta', 'andamento']).count()
        estoque_baixo = Produto.objects.filter(quantidade__lte=0).count()
        return [
            f'Moradores ativos: {moradores_ativos}',
            f'Notas pendentes: {notas_pendentes}',
            f'OS em aberto/andamento: {os_abertas}',
            f'Itens sem estoque: {estoque_baixo}',
        ]

    if page_key == 'calendario':
        eventos = EventoCalendario.objects.order_by('data')[:5]
        if not eventos:
            return ['Nenhum evento cadastrado no calendário.']
        return [f'{_fmt_date(evento.data)} - {evento.titulo}' for evento in eventos]

    if page_key == 'perfil':
        return [
            f'Nome: {morador.nome}',
            f'Quarto: {morador.quarto or "-"}',
            f'Curso: {morador.curso or "-"}',
            f'Funções: {morador.funcoes or "-"}',
        ]

    if page_key == 'moradores':
        ativos = Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome')[:10]
        nomes = ', '.join(item.nome for item in ativos)
        return [
            f'Total de moradores ativos: {Morador.objects.filter(ativo=True).count()}',
            f'Primeiros moradores por hierarquia: {nomes or "-"}',
        ]

    if page_key == 'financeiro':
        pendentes = NotaFiscal.objects.filter(status='pendente')
        total_pendente = pendentes.aggregate(total=Sum('valor'))['total'] or Decimal('0')
        vencendo = pendentes.order_by('data_vencimento')[:5]
        lines = [
            f'Notas pendentes: {pendentes.count()}',
            f'Valor pendente total: {_fmt_money(total_pendente)}',
        ]
        lines.extend(
            f'Vencimento {_fmt_date(nota.data_vencimento)} | {nota.descricao} | {_fmt_money(nota.valor)}'
            for nota in vencendo
        )
        return lines

    if page_key == 'compras':
        compras = NotaFiscal.objects.filter(setor='compras').order_by('-data_emissao')[:5]
        total = NotaFiscal.objects.filter(setor='compras').aggregate(total=Sum('valor'))['total'] or Decimal('0')
        lines = [
            f'Total de notas de compras: {NotaFiscal.objects.filter(setor="compras").count()}',
            f'Valor acumulado em compras: {_fmt_money(total)}',
        ]
        lines.extend(
            f'{_fmt_date(nota.data_emissao)} | {nota.descricao} | {_fmt_money(nota.valor)}'
            for nota in compras
        )
        return lines

    if page_key == 'rock':
        eventos = RockEvento.objects.order_by('-data')[:5]
        arrecadado = RockEvento.objects.aggregate(total=Sum('valor_arrecadado'))['total'] or Decimal('0')
        lines = [
            f'Eventos cadastrados: {RockEvento.objects.count()}',
            f'Valor arrecadado total: {_fmt_money(arrecadado)}',
        ]
        lines.extend(
            f'{_fmt_date(evento.data)} | {evento.nome} | {_fmt_money(evento.valor_arrecadado)}'
            for evento in eventos
        )
        return lines

    if page_key == 'almoxarifado':
        baixo = Produto.objects.filter(quantidade__lte=0).count()
        consumos_morador = ConsumoEstoque.objects.filter(morador=morador).order_by('-data')[:5]
        lines = [
            f'Itens sem estoque: {baixo}',
            f'Seus últimos consumos: {consumos_morador.count()}',
        ]
        lines.extend(
            f'{_fmt_date(consumo.data)} | {consumo.produto.nome} | qtd {consumo.quantidade}'
            for consumo in consumos_morador
        )
        return lines

    if page_key == 'manutencao':
        abertas = OrdemServico.objects.filter(status__in=['aberta', 'andamento']).order_by('-numero')[:5]
        lines = [
            f'OS abertas/em andamento: {OrdemServico.objects.filter(status__in=["aberta", "andamento"]).count()}',
        ]
        lines.extend(
            f'OS #{ordem.numero} | {ordem.status} | {ordem.executado_por}'
            for ordem in abertas
        )
        return lines

    return ['Página não suportada para relatório.']


def _build_report_for_morador(page_key, morador):
    titulo = PAGE_META[page_key]['titulo']
    hoje = timezone.localdate()
    lines = _to_lines(page_key, morador)

    assunto = f'Relatório {titulo} - {hoje.strftime("%d/%m/%Y")}'
    corpo_texto = '\n'.join([
        f'Olá, {morador.apelido or morador.nome}!',
        '',
        f'Segue o relatório da página {titulo}:',
        '',
        *[f'- {line}' for line in lines],
        '',
        'Mensagem automática do ERP.',
    ])

    html_linhas = ''.join(f'<li>{line}</li>' for line in lines)
    corpo_html = (
        f'<p>Olá, <strong>{morador.apelido or morador.nome}</strong>!</p>'
        f'<p>Segue o relatório da página <strong>{titulo}</strong>:</p>'
        f'<ul>{html_linhas}</ul>'
        '<p style="color:#666">Mensagem automática do ERP.</p>'
    )

    return {
        'morador': {
            'id': morador.id,
            'nome': morador.nome,
            'apelido': morador.apelido,
            'email': morador.email,
        },
        'assunto': assunto,
        'corpo_texto': corpo_texto,
        'corpo_html': corpo_html,
        'linhas': lines,
    }


@require_GET
def api_paginas(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    paginas = [
        {
            'chave': key,
            'titulo': meta['titulo'],
            'endpoint_relatorio': ENDPOINTS[key],
        }
        for key, meta in PAGE_META.items()
    ]
    return _json({'paginas': paginas})


@require_GET
def api_moradores(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    moradores = Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome')
    data = [
        {
            'id': morador.id,
            'nome': morador.nome,
            'apelido': morador.apelido,
            'email': morador.email,
            'quarto': morador.quarto,
        }
        for morador in moradores
    ]
    return _json({'count': len(data), 'results': data})


def _api_relatorio_pagina(request, page_key):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _json({'detail': 'JSON inválido.'}, status=400)

    morador_ids = body.get('moradores') or []
    if not isinstance(morador_ids, list) or not morador_ids:
        return _json({'detail': 'Informe "moradores" com uma lista de IDs.'}, status=400)

    moradores = list(Morador.objects.filter(id__in=morador_ids, ativo=True).order_by('ordem_hierarquia', 'nome'))
    if not moradores:
        return _json({'detail': 'Nenhum morador ativo encontrado para os IDs enviados.'}, status=404)

    relatorios = [_build_report_for_morador(page_key, morador) for morador in moradores]
    return _json(
        {
            'pagina': page_key,
            'titulo': PAGE_META[page_key]['titulo'],
            'gerado_em': timezone.now().isoformat(),
            'relatorios': relatorios,
        }
    )


@require_http_methods(['POST'])
def api_relatorio_home(request):
    return _api_relatorio_pagina(request, 'home')


@require_http_methods(['POST'])
def api_relatorio_calendario(request):
    return _api_relatorio_pagina(request, 'calendario')


@require_http_methods(['POST'])
def api_relatorio_perfil(request):
    return _api_relatorio_pagina(request, 'perfil')


@require_http_methods(['POST'])
def api_relatorio_moradores(request):
    return _api_relatorio_pagina(request, 'moradores')


@require_http_methods(['POST'])
def api_relatorio_financeiro(request):
    return _api_relatorio_pagina(request, 'financeiro')


@require_http_methods(['POST'])
def api_relatorio_compras(request):
    return _api_relatorio_pagina(request, 'compras')


@require_http_methods(['POST'])
def api_relatorio_rock(request):
    return _api_relatorio_pagina(request, 'rock')


@require_http_methods(['POST'])
def api_relatorio_almoxarifado(request):
    return _api_relatorio_pagina(request, 'almoxarifado')


@require_http_methods(['POST'])
def api_relatorio_manutencao(request):
    return _api_relatorio_pagina(request, 'manutencao')
