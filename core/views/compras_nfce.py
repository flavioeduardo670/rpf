"""Registro de compra a partir da nota fiscal: QR Code, foto do cupom,
texto copiado da SEFAZ (atalho/compartilhar) ou arquivo XML."""
import os
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.forms import get_choice_options, termos_do_cliente
from core.models import ControleDistribuicaoNFe, NotaFiscal
from core.services.nfce import (
    DadosNFCe,
    QRCodeNFCeInvalido,
    TextoNFCeInvalido,
    aplicar_texto_copiado,
    buscar_nome_empresa,
    consultar_nfce,
    formatar_cnpj,
    interpretar_qrcode_nfce,
    link_sefaz_seguro,
)
from core.services.nfce_foto import (
    FotoNotaInvalida,
    extrair_nota_da_foto,
    leitura_por_foto_configurada,
    nota_foto_para_dados,
)
from core.services.nfe_xml import XMLNotaInvalido, ler_xml_nota

from .common import setor_required
from .financeiro import _primeiro_vencimento, criar_parcelas_nota

CHAVE_SESSAO = 'nfce_leitura'


class ConfirmarCompraNFCeForm(forms.Form):
    MODO_CHOICES = [
        ('total', 'Uma compra com o valor total da nota'),
        ('itens', 'Um registro para cada item da nota'),
    ]
    STATUS_CHOICES = NotaFiscal.STATUS_CHOICES

    fornecedor = forms.CharField(max_length=100)
    descricao = forms.CharField(max_length=200, label='Descrição da compra')
    data_emissao = forms.DateField(label='Data da compra', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    valor_total = forms.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'), label='Valor total (R$)')
    modo = forms.ChoiceField(choices=MODO_CHOICES, initial='total', widget=forms.RadioSelect, label='Como registrar')
    categoria_compra = forms.ChoiceField(label='Categoria')
    tipo_item = forms.ChoiceField(label='Tipo de item')
    cobrar_no_aluguel = forms.BooleanField(required=False, initial=True, label='Cobrar no aluguel (entra no rateio)')
    status = forms.ChoiceField(choices=STATUS_CHOICES, initial='pendente')
    forma_pagamento = forms.CharField(max_length=50, required=False, label='Forma de pagamento')

    def __init__(self, *args, tem_itens=False, **kwargs):
        super().__init__(*args, **kwargs)
        termos = termos_do_cliente()
        self.fields['cobrar_no_aluguel'].label = 'Cobrar {no_cobranca} (entra no rateio)'.format_map(termos)
        self.fields['categoria_compra'].choices = get_choice_options('categoria_compra', [('geral', 'Geral'), ('rock', termos['Evento'])])
        self.fields['tipo_item'].choices = get_choice_options(
            'nota_tipo_item',
            [('Bem de Consumo', 'Bem de Consumo'), ('Bem de Uso', 'Bem de Uso'), ('Bem Material', 'Bem Material'), ('Bem de Troca', 'Bem de Troca')],
        )
        self.fields['tipo_item'].initial = 'Bem de Consumo'
        if not tem_itens:
            self.fields['modo'].choices = self.MODO_CHOICES[:1]


def _formatar_quantidade(quantidade: Decimal) -> str:
    texto = f'{quantidade.normalize():f}'
    return texto.replace('.', ',')


def _descricao_padrao(dados: DadosNFCe) -> str:
    if dados.itens and len(dados.itens) == 1:
        return dados.itens[0].descricao
    if dados.itens:
        return f'Compra com {len(dados.itens)} itens'
    if dados.numero:
        return f'Compra NFC-e nº {dados.numero}'
    return 'Compra'


def _observacao(dados: DadosNFCe, origem: str = '') -> str:
    origem = origem or dados.origem or 'QR Code da NFC-e'
    chave = f' Chave de acesso: {dados.chave_acesso}' if dados.chave_acesso else ' Sem chave de acesso.'
    linhas = [f'Importada de: {origem}.{chave}']
    for item in dados.itens:
        linhas.append(
            f'- {_formatar_quantidade(item.quantidade)} {item.unidade} x {item.descricao}: R$ {item.valor_total:.2f}'.replace('  ', ' ')
        )
    return '\n'.join(linhas)


def registrar_compra_nfce(dados: DadosNFCe, cd: dict, origem: str = '') -> list[NotaFiscal]:
    base = {
        'setor': 'compras',
        'fornecedor': cd['fornecedor'],
        'categoria_compra': cd['categoria_compra'],
        'tipo_item': cd['tipo_item'],
        'adicionar_estoque': False,
        'cobrar_no_aluguel': cd['cobrar_no_aluguel'],
        'parcelado': False,
        'quantidade_parcelas': 1,
        'data_emissao': cd['data_emissao'],
        'data_vencimento': cd['data_emissao'],
        'status': cd['status'],
        'data_pagamento': cd['data_emissao'] if cd['status'] == 'pago' else None,
        'forma_pagamento': cd['forma_pagamento'] or None,
        'observacao': _observacao(dados, origem),
        'chave_acesso': dados.chave_acesso,
    }
    notas = []
    with transaction.atomic():
        if cd['modo'] == 'itens' and dados.itens:
            for item in dados.itens:
                inteira = item.quantidade == item.quantidade.to_integral_value() and item.quantidade > 0
                bate_total = inteira and (item.valor_unitario * item.quantidade).quantize(Decimal('0.01')) == item.valor_total
                if bate_total:
                    quantidade, valor, descricao = int(item.quantidade), item.valor_unitario, item.descricao
                else:
                    # Peso (kg) ou desconto no item: registra o total da linha.
                    quantidade, valor = 1, item.valor_total
                    descricao = f'{item.descricao} ({_formatar_quantidade(item.quantidade)} {item.unidade})'.strip()
                notas.append(NotaFiscal.objects.create(descricao=descricao[:200], quantidade=quantidade, valor=valor, **base))
        else:
            notas.append(NotaFiscal.objects.create(descricao=cd['descricao'], quantidade=1, valor=cd['valor_total'], **base))
        for nota in notas:
            criar_parcelas_nota(nota)
    return notas


def _form_inicial(dados: DadosNFCe):
    return ConfirmarCompraNFCeForm(tem_itens=bool(dados.itens), initial={
        'fornecedor': dados.fornecedor or f'CNPJ {formatar_cnpj(dados.cnpj_emitente)}',
        'descricao': _descricao_padrao(dados),
        'data_emissao': dados.data_emissao,
        'valor_total': dados.valor_total,
    })


def _contexto_leitura(dados: DadosNFCe, form):
    soma_itens = sum((item.valor_total for item in dados.itens), Decimal('0.00'))
    link_sefaz = dados.url_consulta if not dados.consulta_sefaz_ok and link_sefaz_seguro(dados.url_consulta) else ''
    if dados.valor_total is None and not link_sefaz:
        form.fields['valor_total'].widget.attrs['autofocus'] = 'autofocus'
    return {
        'dados': dados,
        'form': form,
        'link_sefaz': link_sefaz,
        'foto_configurada': leitura_por_foto_configurada(),
        'cnpj_formatado': formatar_cnpj(dados.cnpj_emitente),
        'soma_itens': soma_itens,
        'diferenca_itens': bool(dados.itens and dados.valor_total is not None and soma_itens != dados.valor_total),
    }


def _nota_existente(dados: DadosNFCe):
    if not dados.chave_acesso:
        return None
    return NotaFiscal.objects.filter(chave_acesso=dados.chave_acesso).order_by('id').first()


def _redirecionar_existente(request, existente):
    messages.warning(request, f'Esta nota já foi registrada ({existente.descricao} - {existente.fornecedor}).')
    request.session.pop(CHAVE_SESSAO, None)
    return redirect('editar_nota_compra', nota_id=existente.id)


def _mostrar_leitura(request, dados: DadosNFCe, mensagem: str = ''):
    if not dados.fornecedor and dados.cnpj_emitente:
        dados.fornecedor = buscar_nome_empresa(dados.cnpj_emitente)
    request.session[CHAVE_SESSAO] = dados.para_sessao()
    if mensagem:
        messages.success(request, mensagem)
    return _contexto_leitura(dados, _form_inicial(dados))


def _url_absoluta(request, caminho: str) -> str:
    return request.build_absolute_uri(caminho)


def _bookmarklet(request) -> str:
    destino = _url_absoluta(request, reverse('compras_nfce_receber'))
    return (
        "javascript:(function(){var f=document.createElement('form');f.method='POST';"
        f"f.action='{destino}';f.acceptCharset='UTF-8';f.style.display='none';"
        "[['url',location.href],['text',document.body.innerText.slice(0,150000)]].forEach(function(p){"
        "var c=document.createElement('textarea');c.name=p[0];c.value=p[1];f.appendChild(c);});"
        "document.body.appendChild(f);f.submit();})();"
    )


def _contexto_inicial(request, extra=None):
    contexto = {
        'foto_configurada': leitura_por_foto_configurada(),
        'bookmarklet': _bookmarklet(request),
        'email_configurado': bool(os.getenv('NFE_EMAIL_IMAP_HOST') and os.getenv('NFE_EMAIL_USUARIO')),
        'email_notas': os.getenv('NFE_EMAIL_USUARIO', ''),
        'receita_configurada': bool(os.getenv('NFE_CNPJ') and (
            os.getenv('NFE_CERTIFICADO_PFX_BASE64') or os.getenv('NFE_CERTIFICADO_PFX_CAMINHO')
        )),
        'controle_receita': ControleDistribuicaoNFe.objects.order_by('-ultima_consulta').first(),
    }
    contexto.update(extra or {})
    return contexto


def _dados_do_qrcode_ou_texto(*fontes: str) -> DadosNFCe | None:
    for fonte in fontes:
        if not fonte:
            continue
        try:
            return interpretar_qrcode_nfce(fonte)
        except QRCodeNFCeInvalido:
            continue
    return None


@setor_required(group_name='Compras', morador_edit_attr='acesso_compras_editar')
def compras_qrcode(request):
    contexto = {}
    acao = request.POST.get('acao') if request.method == 'POST' else ''

    if acao == 'ler':
        conteudo = request.POST.get('conteudo_qrcode', '')
        try:
            dados = interpretar_qrcode_nfce(conteudo)
        except QRCodeNFCeInvalido as exc:
            messages.error(request, str(exc))
            return render(request, 'core/compras_qrcode.html', _contexto_inicial(request, {'conteudo_qrcode': conteudo}))

        existente = _nota_existente(dados)
        if existente:
            return _redirecionar_existente(request, existente)

        dados = consultar_nfce(dados)
        request.session[CHAVE_SESSAO] = dados.para_sessao()
        contexto = _contexto_leitura(dados, _form_inicial(dados))

    elif acao == 'foto':
        arquivo = request.FILES.get('foto_nota')
        bruto = request.session.get(CHAVE_SESSAO) if request.POST.get('completar') == '1' else None
        base = DadosNFCe.da_sessao(bruto) if bruto else None
        if not arquivo:
            messages.error(request, 'Escolha ou tire a foto da nota.')
            return redirect('compras_qrcode')
        try:
            dados = nota_foto_para_dados(extrair_nota_da_foto(arquivo.read()), base=base)
        except FotoNotaInvalida as exc:
            messages.error(request, str(exc))
            if base is not None:
                contexto = _contexto_leitura(base, _form_inicial(base))
            else:
                return render(request, 'core/compras_qrcode.html', _contexto_inicial(request))
        else:
            dados.origem = 'foto da nota'
            existente = _nota_existente(dados)
            if existente and base is None:
                return _redirecionar_existente(request, existente)
            contexto = _mostrar_leitura(request, dados, f'Nota lida pela foto: {len(dados.itens)} item(ns). Confira antes de registrar.')

    elif acao == 'xml':
        arquivo = request.FILES.get('xml_nota')
        if not arquivo:
            messages.error(request, 'Escolha o arquivo XML da nota.')
            return redirect('compras_qrcode')
        try:
            dados = ler_xml_nota(arquivo.read())
        except XMLNotaInvalido as exc:
            messages.error(request, str(exc))
            return render(request, 'core/compras_qrcode.html', _contexto_inicial(request))
        dados.origem = 'arquivo XML da nota'
        existente = _nota_existente(dados)
        if existente:
            return _redirecionar_existente(request, existente)
        contexto = _mostrar_leitura(request, dados, f'XML lido: {len(dados.itens)} item(ns).')

    elif acao == 'importar':
        # Vem do atalho do navegador ou do "Compartilhar" do celular.
        url = request.POST.get('conteudo_qrcode', '')[:4000]
        texto = request.POST.get('texto_nota', '')
        dados = _dados_do_qrcode_ou_texto(url, texto) or DadosNFCe(chave_acesso='')
        existente = _nota_existente(dados)
        if existente:
            return _redirecionar_existente(request, existente)
        try:
            dados = aplicar_texto_copiado(dados, texto)
        except TextoNFCeInvalido as exc:
            messages.error(request, str(exc))
            if not dados.chave_acesso:
                return render(request, 'core/compras_qrcode.html', _contexto_inicial(request))
            dados = consultar_nfce(dados)
            request.session[CHAVE_SESSAO] = dados.para_sessao()
            contexto = _contexto_leitura(dados, _form_inicial(dados))
        else:
            dados.origem = 'página da SEFAZ (atalho)'
            contexto = _mostrar_leitura(request, dados, f'Nota lida: {len(dados.itens)} item(ns).')

    elif acao == 'colar':
        bruto = request.session.get(CHAVE_SESSAO)
        if not bruto:
            messages.error(request, 'A leitura expirou. Leia o QR Code de novo.')
            return redirect('compras_qrcode')
        dados = DadosNFCe.da_sessao(bruto)
        try:
            dados = aplicar_texto_copiado(dados, request.POST.get('texto_nota', ''))
        except TextoNFCeInvalido as exc:
            messages.error(request, str(exc))
            contexto = _contexto_leitura(dados, _form_inicial(dados))
            contexto['texto_nota'] = request.POST.get('texto_nota', '')[:5000]
        else:
            dados.origem = 'página da SEFAZ (texto colado)'
            contexto = _mostrar_leitura(request, dados, f'Nota lida: {len(dados.itens)} item(ns).')

    elif acao == 'confirmar':
        bruto = request.session.get(CHAVE_SESSAO)
        if not bruto:
            messages.error(request, 'A leitura expirou. Leia o QR Code de novo.')
            return redirect('compras_qrcode')
        dados = DadosNFCe.da_sessao(bruto)
        form = ConfirmarCompraNFCeForm(request.POST, tem_itens=bool(dados.itens))
        if form.is_valid():
            if _nota_existente(dados):
                messages.warning(request, 'Esta nota já foi registrada.')
                request.session.pop(CHAVE_SESSAO, None)
                return redirect('compras')
            notas = registrar_compra_nfce(dados, form.cleaned_data)
            request.session.pop(CHAVE_SESSAO, None)
            total = sum((n.valor * (n.quantidade or 1) for n in notas), Decimal('0.00'))
            messages.success(
                request,
                f'Compra registrada: {len(notas)} registro(s), total R$ {total:.2f}'.replace('.', ',')
                + f' - {form.cleaned_data["fornecedor"]}.',
            )
            _, mes_cobranca = _primeiro_vencimento(form.cleaned_data['data_emissao'])
            return redirect(f"{reverse('compras')}?mes={mes_cobranca.strftime('%Y-%m')}")
        contexto = _contexto_leitura(dados, form)

    if not contexto:
        contexto = _contexto_inicial(request)
    return render(request, 'core/compras_qrcode.html', contexto)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def compras_nfce_receber(request):
    """Recebe o texto da nota enviado pelo atalho do navegador (na página da
    SEFAZ, depois do "não sou robô") ou pelo Compartilhar do celular (app
    instalado). Não grava nada: só mostra o que chegou e a pessoa toca em
    "Importar nota", que segue para o Compras com login e CSRF normais."""
    texto = request.POST.get('text', '') if request.method == 'POST' else ''
    url = request.POST.get('url', '') if request.method == 'POST' else ''
    titulo = request.POST.get('title', '') if request.method == 'POST' else ''
    if not url and texto.strip().lower().startswith('http'):
        url, texto = texto.strip().split()[0], ''
    return render(request, 'core/compras_nfce_receber.html', {
        'texto': texto[:200000],
        'url': url[:4000],
        'titulo': titulo[:200],
        'tem_nota': bool(texto.strip() or url.strip()),
    })


def pwa_manifest(request):
    import json

    from django.conf import settings

    from core.models import Organizacao

    organizacao = Organizacao.atual()
    manifest = {
        'name': f'{organizacao.nome} - {settings.PRODUTO_NOME}',
        'short_name': organizacao.nome_curto,
        'start_url': reverse('home'),
        'scope': '/',
        'display': 'standalone',
        'background_color': '#000000',
        'theme_color': '#000000',
        'icons': [
            {'src': static('core/brand/app-192.png'), 'sizes': '192x192', 'type': 'image/png'},
            {'src': static('core/brand/app-512.png'), 'sizes': '512x512', 'type': 'image/png'},
        ],
    }
    if 'compras' in organizacao.modulos_ativos:
        # "Compartilhar → <app>" para importar a nota da SEFAZ só faz sentido com Compras ligado.
        manifest['share_target'] = {
            'action': reverse('compras_nfce_receber'),
            'method': 'POST',
            'enctype': 'application/x-www-form-urlencoded',
            'params': {'title': 'title', 'text': 'text', 'url': 'url'},
        }
    return HttpResponse(json.dumps(manifest, ensure_ascii=False), content_type='application/manifest+json')


def pwa_service_worker(request):
    # Necessário para o celular oferecer "Instalar app"; não guarda nada em cache.
    codigo = "self.addEventListener('install',()=>self.skipWaiting());" \
             "self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));" \
             "self.addEventListener('fetch',()=>{});"
    resposta = HttpResponse(codigo, content_type='application/javascript')
    resposta['Service-Worker-Allowed'] = '/'
    resposta['Cache-Control'] = 'no-cache'
    return resposta
