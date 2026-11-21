"""Registro de compra a partir do QR Code da NFC-e."""
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from core.forms import get_choice_options
from core.models import NotaFiscal
from core.services.nfce import (
    DadosNFCe,
    QRCodeNFCeInvalido,
    consultar_nfce,
    formatar_cnpj,
    interpretar_qrcode_nfce,
    link_sefaz_seguro,
)

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
        self.fields['categoria_compra'].choices = get_choice_options('categoria_compra', [('geral', 'Geral'), ('rock', 'Rock')])
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
    return f'Compra NFC-e nº {dados.numero}'


def _observacao(dados: DadosNFCe) -> str:
    linhas = [f'Importada do QR Code da NFC-e. Chave de acesso: {dados.chave_acesso}']
    for item in dados.itens:
        linhas.append(
            f'- {_formatar_quantidade(item.quantidade)} {item.unidade} x {item.descricao}: R$ {item.valor_total:.2f}'.replace('  ', ' ')
        )
    return '\n'.join(linhas)


def registrar_compra_nfce(dados: DadosNFCe, cd: dict) -> list[NotaFiscal]:
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
        'observacao': _observacao(dados),
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


def _contexto_leitura(dados: DadosNFCe, form):
    soma_itens = sum((item.valor_total for item in dados.itens), Decimal('0.00'))
    if dados.valor_total is None:
        form.fields['valor_total'].widget.attrs['autofocus'] = 'autofocus'
    return {
        'dados': dados,
        'form': form,
        'link_sefaz': dados.url_consulta if not dados.consulta_sefaz_ok and link_sefaz_seguro(dados.url_consulta) else '',
        'cnpj_formatado': formatar_cnpj(dados.cnpj_emitente),
        'soma_itens': soma_itens,
        'diferenca_itens': bool(dados.itens and dados.valor_total is not None and soma_itens != dados.valor_total),
    }


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
            return render(request, 'core/compras_qrcode.html', {'conteudo_qrcode': conteudo})

        existente = NotaFiscal.objects.filter(chave_acesso=dados.chave_acesso).order_by('id').first()
        if existente:
            messages.warning(request, f'Esta nota já foi registrada ({existente.descricao} - {existente.fornecedor}).')
            return redirect('editar_nota_compra', nota_id=existente.id)

        dados = consultar_nfce(dados)
        request.session[CHAVE_SESSAO] = dados.para_sessao()
        form = ConfirmarCompraNFCeForm(tem_itens=bool(dados.itens), initial={
            'fornecedor': dados.fornecedor or f'CNPJ {formatar_cnpj(dados.cnpj_emitente)}',
            'descricao': _descricao_padrao(dados),
            'data_emissao': dados.data_emissao,
            'valor_total': dados.valor_total,
        })
        contexto = _contexto_leitura(dados, form)

    elif acao == 'confirmar':
        bruto = request.session.get(CHAVE_SESSAO)
        if not bruto:
            messages.error(request, 'A leitura expirou. Leia o QR Code de novo.')
            return redirect('compras_qrcode')
        dados = DadosNFCe.da_sessao(bruto)
        form = ConfirmarCompraNFCeForm(request.POST, tem_itens=bool(dados.itens))
        if form.is_valid():
            if NotaFiscal.objects.filter(chave_acesso=dados.chave_acesso).exists():
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

    return render(request, 'core/compras_qrcode.html', contexto)
