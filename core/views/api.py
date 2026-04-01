from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core.models import ConsumoEstoque, Morador, NotaFiscal, OrdemServico, Produto, RockEvento
from core.services.financeiro import calcular_rateio_financeiro, resolver_mes_referencia


def _parse_limit(request, default=100, maximum=500):
    try:
        limit = int(request.GET.get('limit', default))
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, maximum))


def _check_api_key(request):
    configured_key = getattr(settings, 'ERP_API_KEY', '')
    if not configured_key:
        return JsonResponse(
            {'detail': 'ERP_API_KEY não configurada no servidor.'},
            status=503,
        )

    provided_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
    if provided_key != configured_key:
        return JsonResponse({'detail': 'Não autorizado.'}, status=401)
    return None


def _json(data, status=200):
    return JsonResponse(data, status=status, encoder=DjangoJSONEncoder, json_dumps_params={'ensure_ascii': False})


def _build_api_endpoints():
    return {
        'root': '/api/',
        'status': '/api/status/',
        'auth_check': '/api/auth-check/',
        'setores': '/api/setores/',
        'moradores': '/api/setores/moradores/',
        'financeiro': '/api/setores/financeiro/',
        'financeiro_rateio': '/api/setores/financeiro/rateio/',
        'compras': '/api/setores/compras/',
        'estoque': '/api/setores/estoque/',
        'manutencao': '/api/setores/manutencao/',
        'rock': '/api/setores/rock/',
        # aliases legados
        'legacy_financeiro': '/api/financeiro/',
        'legacy_financeiro_rateio': '/api/financeiro/rateio/',
        'legacy_finnaceiro': '/api/finnaceiro/',
        'legacy_finnaceiro_rateio': '/api/finnaceiro/rateio/',
        'legacy_rateio': '/api/rateio/',
    }



@require_GET
def api_status(request):
    return _json({'status': 'ok', 'api': 'rpf-readonly'})


@require_GET
def api_auth_check(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized
    return _json({'auth': 'ok'})


@require_GET
def api_root(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    return _json(
        {
            'api': 'rpf-readonly',
            'version': 1,
            'auth': {
                'header': 'X-API-Key',
                'query_param': 'api_key',
            },
            'endpoints': _build_api_endpoints(),
        }
    )


@require_GET
def api_setores(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    endpoints = _build_api_endpoints()
    return _json(
        {
            'setores': [
                'moradores',
                'financeiro',
                'compras',
                'estoque',
                'manutencao',
                'rock',
            ],
            'endpoints': endpoints,
            'observacao': 'Envie X-API-Key no header (ou api_key na query string).',
        }
    )


@require_GET
def api_moradores(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    limit = _parse_limit(request)
    moradores = Morador.objects.select_related('user').order_by('ordem_hierarquia', 'nome')[:limit]
    data = [
        {
            'id': morador.id,
            'nome': morador.nome,
            'apelido': morador.apelido,
            'email': morador.email,
            'quarto': morador.quarto,
            'codigo_quarto': morador.codigo_quarto,
            'peso_quarto': morador.peso_quarto,
            'curso': morador.curso,
            'funcoes': morador.funcoes,
            'ativo': morador.ativo,
            'ordem_hierarquia': morador.ordem_hierarquia,
            'username': morador.user.username if morador.user else None,
        }
        for morador in moradores
    ]
    return _json({'setor': 'moradores', 'count': len(data), 'results': data})


@require_GET
def api_financeiro(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    limit = _parse_limit(request)
    notas = NotaFiscal.objects.filter(setor__in=['compras', 'manutencao', 'outros']).order_by('-id')[:limit]
    data = [
        {
            'id': nota.id,
            'setor': nota.setor,
            'descricao': nota.descricao,
            'fornecedor': nota.fornecedor,
            'valor': nota.valor,
            'quantidade': nota.quantidade,
            'parcelado': nota.parcelado,
            'quantidade_parcelas': nota.quantidade_parcelas,
            'status': nota.status,
            'data_emissao': nota.data_emissao,
            'data_vencimento': nota.data_vencimento,
            'data_pagamento': nota.data_pagamento,
        }
        for nota in notas
    ]
    return _json({'setor': 'financeiro', 'count': len(data), 'results': data})


@require_GET
def api_financeiro_rateio(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    mes_referencia = resolver_mes_referencia(request.GET.get('mes'))
    resumo = calcular_rateio_financeiro(mes_referencia, incluir_pendencia=True)

    moradores = [
        {
            'id': item['morador'].id,
            'nome': item['morador'].nome,
            'apelido': item['morador'].apelido,
            'email': item['morador'].email,
            'codigo_quarto': item['morador'].codigo_quarto,
            'quarto': item['morador'].quarto,
            'peso_quarto': item['morador'].peso_quarto,
            'aluguel': item['aluguel'],
            'fixas': item['fixas'],
            'fixas_detalhe': item['fixas_detalhe'],
            'caixinha': item['caixinha'],
            'parcelas': item['parcelas'],
            'desconto': item['desconto'],
            'extra': item['extra'],
            'valor_total': item['valor'],
        }
        for item in resumo['rateio_moradores']
    ]

    return _json(
        {
            'setor': 'financeiro',
            'tipo': 'rateio',
            'mes_referencia': mes_referencia,
            'resumo': {
                'valor_aluguel': resumo['valor_aluguel'],
                'valor_fixas_total': resumo['valor_fixas_total'],
                'total_caixinha_mes': resumo['total_caixinha_mes'],
                'total_parcelas_material': resumo['total_parcelas_material'],
                'desconto_total_mes': resumo['desconto_total_mes'],
                'pendencia_total_mes': resumo['pendencia_total_mes'],
                'total_rateio': resumo['total_rateio'],
                'total_moradores_ativos': resumo['total_moradores_ativos'],
                'valor_por_morador': resumo['valor_por_morador'],
                'caixinha_por_morador': resumo['caixinha_por_morador'],
            },
            'contas_fixas': [
                {'nome': conta.nome, 'valor': conta.valor}
                for conta in resumo['contas_fixas']
            ],
            'moradores': moradores,
        }
    )


@require_GET
def api_compras(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    limit = _parse_limit(request)
    notas = NotaFiscal.objects.filter(setor='compras').order_by('-id')[:limit]
    data = [
        {
            'id': nota.id,
            'descricao': nota.descricao,
            'fornecedor': nota.fornecedor,
            'categoria_compra': nota.categoria_compra,
            'tipo_item': nota.tipo_item,
            'quantidade': nota.quantidade,
            'valor': nota.valor,
            'status': nota.status,
            'data_emissao': nota.data_emissao,
            'data_vencimento': nota.data_vencimento,
        }
        for nota in notas
    ]
    return _json({'setor': 'compras', 'count': len(data), 'results': data})


@require_GET
def api_estoque(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    limit = _parse_limit(request)
    produtos = Produto.objects.select_related('setor', 'local').order_by('nome')[:limit]
    consumos = ConsumoEstoque.objects.select_related('morador', 'produto').order_by('-id')[:limit]
    return _json(
        {
            'setor': 'estoque',
            'produtos_count': len(produtos),
            'consumos_count': len(consumos),
            'produtos': [
                {
                    'id': produto.id,
                    'nome': produto.nome,
                    'descricao': produto.descricao,
                    'setor': produto.setor.nome,
                    'local': produto.local.nome if produto.local else None,
                    'quantidade': produto.quantidade,
                    'estoque_minimo': produto.estoque_minimo,
                }
                for produto in produtos
            ],
            'consumos': [
                {
                    'id': consumo.id,
                    'morador': consumo.morador.nome,
                    'produto': consumo.produto.nome,
                    'quantidade': consumo.quantidade,
                    'data': consumo.data,
                    'setor': consumo.setor,
                }
                for consumo in consumos
            ],
        }
    )


@require_GET
def api_manutencao(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    limit = _parse_limit(request)
    ordens = OrdemServico.objects.order_by('-numero')[:limit]
    data = [
        {
            'numero': os.numero,
            'setor': os.setor,
            'status': os.status,
            'descricao': os.descricao,
            'observacao': os.observacao,
            'executado_por': os.executado_por,
            'data_inicio': os.data_inicio,
            'data_fim': os.data_fim,
            'despesa_gerada': os.despesa_gerada,
        }
        for os in ordens
    ]
    return _json({'setor': 'manutencao', 'count': len(data), 'results': data})


@require_GET
def api_rock(request):
    unauthorized = _check_api_key(request)
    if unauthorized:
        return unauthorized

    limit = _parse_limit(request)
    eventos = RockEvento.objects.order_by('-data', '-id')[:limit]
    data = [
        {
            'id': evento.id,
            'nome': evento.nome,
            'tipo': evento.tipo,
            'quantidade_pessoas': evento.quantidade_pessoas,
            'valor_arrecadado': evento.valor_arrecadado,
            'data': evento.data,
            'observacoes': evento.observacoes,
        }
        for evento in eventos
    ]
    return _json({'setor': 'rock', 'count': len(data), 'results': data})
