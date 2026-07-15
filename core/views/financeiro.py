import csv
from datetime import datetime, timedelta
from decimal import Decimal

import segno

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Case, DecimalField, ExpressionWrapper, F, OuterRef, Subquery, Sum, When
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from core.forms import (
    AjusteMoradorForm,
    ConfiguracaoFinanceiraForm,
    ContaFixaMensalForm,
    ContaCasaForm,
    DescontoMensalForm,
    PendenciaMensalItemForm,
    apply_form_config,
    get_choice_options,
)
from core.models import (
    AjusteMorador,
    Comodo,
    ComprovantePagamentoMorador,
    CobrancaAluguel,
    ConfiguracaoFinanceira,
    ContaFixaMensal,
    ContaCasa,
    LocalArmazenamento,
    Mensalidade,
    Morador,
    NotaFiscal,
    NotaParcela,
    ParcelaRateioExclusao,
    PendenciaMensalItem,
    RegistroFinanceiroMensal,
    Produto,
    RockEvento,
    Setor,
)
from core.services.estoque import garantir_setores_e_locais_base
from core.services.pix_gateway import criar_cobranca_pix_avulsa, normalizar_chave_pix
from core.services.financeiro import (
    calcular_rateio_financeiro,
    garantir_contas_fixas_mensais,
    resolver_mes_referencia,
    salvar_registro_financeiro_mensal,
)

from .common import can_edit, setor_required
from .common import get_user_morador


ContaFixaMensalFormSet = forms.modelformset_factory(ContaFixaMensal, form=ContaFixaMensalForm, extra=1, can_delete=True)
ContaCasaFormSet = forms.modelformset_factory(ContaCasa, form=ContaCasaForm, extra=1, can_delete=True)
AjusteMoradorFormSet = forms.modelformset_factory(AjusteMorador, form=AjusteMoradorForm, extra=1, can_delete=True)
PendenciaMensalItemFormSet = forms.modelformset_factory(PendenciaMensalItem, form=PendenciaMensalItemForm, extra=1, can_delete=True)


class ParcelaForm(forms.ModelForm):
    class Meta:
        model = NotaParcela
        fields = ['valor', 'vencimento', 'mes_referencia', 'status']
        widgets = {
            'vencimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'mes_referencia': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }


class NotaFiscalForm(forms.ModelForm):
    comodo_estoque = forms.ModelChoiceField(queryset=Comodo.objects.none(), required=False, label='Cômodo')
    rock_evento = forms.ModelChoiceField(queryset=RockEvento.objects.none(), required=False, label='Rock', empty_label='Geral')

    class Meta:
        model = NotaFiscal
        fields = [
            'descricao', 'fornecedor', 'categoria_compra', 'setor_estoque', 'comodo_estoque', 'local_estoque', 'rock_evento',
            'tipo_item', 'quantidade', 'qualidade', 'adicionar_estoque', 'cobrar_no_aluguel', 'parcelado', 'quantidade_parcelas',
            'valor', 'data_emissao', 'data_vencimento', 'status', 'data_pagamento', 'forma_pagamento', 'observacao',
        ]
        labels = {'descricao': 'Item', 'valor': 'Valor unitario'}
        widgets = {
            k: forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})
            for k in ['data_emissao', 'data_vencimento', 'data_pagamento']
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setores = {s.nome: s for s in Setor.objects.filter(nome__in=['Infraestrutura', 'Hotelaria', 'Rock'])}
        self.fields['setor_estoque'].choices = [(setores[n].id, setores[n].nome) for n in ['Infraestrutura', 'Hotelaria', 'Rock'] if n in setores]
        self.fields['setor_estoque'].required = False
        self.fields['comodo_estoque'].queryset = Comodo.objects.select_related('andar').order_by('andar__nome', 'nome')
        selected_comodo = None
        if self.data and self.data.get(self.add_prefix('comodo_estoque')):
            selected_comodo = Comodo.objects.filter(pk=self.data.get(self.add_prefix('comodo_estoque'))).first()
        elif self.instance and self.instance.pk and self.instance.local_estoque and self.instance.local_estoque.comodo_id:
            selected_comodo = self.instance.local_estoque.comodo
        self.fields['local_estoque'].queryset = LocalArmazenamento.objects.filter(comodo=selected_comodo).order_by('nome') if selected_comodo else LocalArmazenamento.objects.none()
        self.fields['local_estoque'].required = False
        self.fields['rock_evento'].queryset = RockEvento.objects.order_by('-data', 'nome')
        self.fields['tipo_item'] = forms.ChoiceField(choices=get_choice_options('nota_tipo_item', [('', '---'), ('Bem de Uso', 'Bem de Uso'), ('Bem Material', 'Bem Material'), ('Bem de Consumo', 'Bem de Consumo'), ('Bem de Troca', 'Bem de Troca')]), required=True)
        self.fields['categoria_compra'].choices = get_choice_options('categoria_compra', [('geral', 'Geral'), ('rock', 'Rock')])
        self.fields['quantidade_parcelas'].min_value = 1
        self.fields['quantidade_parcelas'].label = 'Quantidade de parcelas'
        adicionar = self._get_adicionar_estoque_value()
        self.fields['setor_estoque'].required = adicionar
        self.fields['comodo_estoque'].required = adicionar
        self.fields['local_estoque'].required = adicionar
        self.fields['quantidade'].required = adicionar
        apply_form_config(self, 'nota_fiscal_form')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('categoria_compra') != 'rock':
            cleaned['rock_evento'] = None
        return cleaned

    def _get_adicionar_estoque_value(self):
        if self.data:
            val = self.data.get(self.add_prefix('adicionar_estoque'))
            if val is not None:
                return val in ('on', 'true', 'True', '1')
        if self.instance and self.instance.pk:
            return bool(self.instance.adicionar_estoque)
        return True


@setor_required(group_name='Financeiro', morador_view_attr='acesso_financeiro_visualizar', morador_edit_attr='acesso_financeiro_editar')
def financeiro_home(request):
    modulos = [
        {
            'titulo': 'Aluguel',
            'descricao': 'Rateio mensal, ajustes individuais, pendências e comprovantes.',
            'url': redirect('financeiro_aluguel').url,
            'status': 'Ativo',
        },
        {
            'titulo': 'Faturamento',
            'descricao': 'Acompanhamento de receitas e previsão de entradas.',
            'url': '',
            'status': 'Em breve',
        },
        {
            'titulo': 'Prestação de contas',
            'descricao': 'Consolidação de despesas e prestação por período.',
            'url': redirect('financeiro_prestacao_contas').url,
            'status': 'Ativo',
        },
        {
            'titulo': 'Registros mensais',
            'descricao': 'Histórico salvo de como o rateio ficou em cada mês.',
            'url': redirect('financeiro_registros_mensais').url,
            'status': 'Ativo',
        },
        {
            'titulo': 'Fluxo de caixa',
            'descricao': 'Visão de entradas e saídas com saldo acumulado.',
            'url': '',
            'status': 'Em breve',
        },
        {
            'titulo': 'Balanço patrimonial',
            'descricao': 'Resumo patrimonial e posição financeira da casa.',
            'url': '',
            'status': 'Em breve',
        },
    ]
    return render(request, 'core/financeiro_home.html', {'modulos': modulos})





def _usuario_pode_ver_prestacao_geral(request):
    if request.user.is_superuser or request.user.groups.filter(name='Financeiro').exists():
        return True
    return can_edit(request, 'acesso_financeiro_visualizar') or can_edit(request, 'acesso_financeiro_editar')


def _usuario_pode_ver_extrato_morador(request, morador_id):
    if _usuario_pode_ver_prestacao_geral(request):
        return True
    morador_logado = get_user_morador(request.user)
    return bool(morador_logado and morador_logado.id == morador_id)


def _valor_percentual(valor, total):
    percentual = (valor / total * Decimal('100')) if total else Decimal('0.00')
    return f"{percentual.quantize(Decimal('0.01'))}"


def _dividir_valor_por_moradores(valor, quantidade):
    if not quantidade:
        return Decimal('0.00')
    return (valor / quantidade).quantize(Decimal('0.01'))


def _moradores_participantes_parcela(parcela, moradores_ativos):
    excluidos_ids = {item.morador_id for item in parcela.rateio_exclusoes.all()}
    participantes = [morador for morador in moradores_ativos if morador.id not in excluidos_ids]
    return participantes or moradores_ativos


def _valor_parcela_para_morador(parcela, morador, participantes):
    if not participantes or morador.id not in {participante.id for participante in participantes}:
        return Decimal('0.00')
    valor_total = parcela.valor or Decimal('0.00')
    valor_base = (valor_total / len(participantes)).quantize(Decimal('0.01'))
    participante_ids = [participante.id for participante in participantes]
    if morador.id == participante_ids[-1]:
        return (valor_total - (valor_base * (len(participantes) - 1))).quantize(Decimal('0.01'))
    return valor_base


def _montar_extrato_morador(resumo, item, mes_referencia):
    morador = item['morador']
    moradores_ativos = resumo['moradores_ativos']
    total_moradores = resumo['total_moradores_ativos']
    lancamentos = []

    def adicionar(data, categoria, descricao, valor, tipo='debito', detalhe=''):
        valor = (valor or Decimal('0.00')).quantize(Decimal('0.01'))
        if valor == Decimal('0.00'):
            return
        lancamentos.append({
            'data': data,
            'categoria': categoria,
            'descricao': descricao,
            'detalhe': detalhe,
            'tipo': tipo,
            'valor': valor,
        })

    adicionar(
        mes_referencia,
        'Aluguel',
        'Quota do aluguel do mês',
        item['aluguel'],
        detalhe=f"Peso do quarto: {morador.peso_quarto or Decimal('0.00')}.",
    )

    for conta, valor_morador in zip(resumo['contas_fixas'], item['fixas_detalhe']):
        adicionar(
            mes_referencia,
            'Conta fixa',
            conta.nome,
            valor_morador,
            detalhe=f"R$ {conta.valor.quantize(Decimal('0.01'))} dividido entre {total_moradores} moradores ativos.",
        )

    for parcela in resumo['parcelas_rateio']:
        participantes = _moradores_participantes_parcela(parcela, moradores_ativos)
        valor_morador = _valor_parcela_para_morador(parcela, morador, participantes)
        if valor_morador == Decimal('0.00'):
            continue
        nota = parcela.nota
        detalhes = [
            f"Parcela {parcela.numero}",
            f"mês de cobrança {parcela.mes_referencia.strftime('%m/%Y')}",
            f"dividida entre {len(participantes)} morador(es)",
        ]
        if nota.fornecedor:
            detalhes.append(f"fornecedor: {nota.fornecedor}")
        if nota.tipo_item:
            detalhes.append(f"tipo: {nota.tipo_item}")
        adicionar(
            nota.data_emissao or parcela.vencimento or mes_referencia,
            'Parcelas do mês',
            nota.descricao,
            valor_morador,
            detalhe='; '.join(detalhes) + '.',
        )

    for pendencia in resumo['pendencias_items']:
        valor_morador = _dividir_valor_por_moradores(pendencia.valor, total_moradores)
        descricao = pendencia.motivo or pendencia.descricao or pendencia.get_tipo_display()
        detalhe = pendencia.descricao if pendencia.motivo and pendencia.descricao != pendencia.motivo else ''
        adicionar(
            pendencia.mes_referencia,
            pendencia.get_tipo_display(),
            descricao,
            valor_morador,
            tipo='credito' if pendencia.tipo == 'desconto' else 'debito',
            detalhe=(detalhe or f"Rateado igualmente entre {total_moradores} moradores ativos."),
        )

    ajustes = AjusteMorador.objects.filter(mes_referencia=mes_referencia, morador=morador).order_by('id')
    for ajuste in ajustes:
        adicionar(
            ajuste.mes_referencia,
            'Ajuste individual',
            ajuste.motivo,
            ajuste.valor,
            tipo='credito' if ajuste.tipo == 'desconto' else 'debito',
            detalhe=ajuste.get_tipo_display(),
        )

    lancamentos.sort(key=lambda lancamento: (lancamento['data'], lancamento['categoria'], lancamento['descricao']))
    total_debitos = sum((l['valor'] for l in lancamentos if l['tipo'] == 'debito'), Decimal('0.00')).quantize(Decimal('0.01'))
    total_creditos = sum((l['valor'] for l in lancamentos if l['tipo'] == 'credito'), Decimal('0.00')).quantize(Decimal('0.01'))
    saldo = (total_debitos - total_creditos).quantize(Decimal('0.01'))
    return lancamentos, total_debitos, total_creditos, saldo


def _normalizar_texto_pdf(valor):
    return ' '.join(str(valor).replace('!', '').replace('·', '-').replace('—', '-').split())


def _texto_pdf(valor):
    texto = _normalizar_texto_pdf(valor)
    return texto.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _formatar_moeda_pt_br(valor):
    valor = (valor or Decimal('0.00')).quantize(Decimal('0.01'))
    texto = f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"R$ {texto}"


def _formatar_percentual_pt_br(valor):
    return f"{str(valor).replace('.', ',')}%"


def _quebrar_texto_pdf(texto, largura=72):
    palavras = str(texto or '').split()
    if not palavras:
        return ['']
    linhas = []
    linha_atual = ''
    for palavra in palavras:
        candidata = f"{linha_atual} {palavra}".strip()
        if len(candidata) <= largura:
            linha_atual = candidata
            continue
        if linha_atual:
            linhas.append(linha_atual)
        while len(palavra) > largura:
            linhas.append(palavra[:largura])
            palavra = palavra[largura:]
        linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)
    return linhas


def _largura_texto_pdf(texto, tamanho=9):
    return len(str(texto)) * tamanho * Decimal('0.48')


def _comando_texto_pdf(texto, x, y, tamanho=9, fonte='F1', cor='0.10 0.10 0.10 rg'):
    return f"{cor} BT /{fonte} {tamanho} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({_texto_pdf(texto)}) Tj ET"


def _comando_texto_direita_pdf(texto, x_direita, y, tamanho=9, fonte='F1', cor='0.10 0.10 0.10 rg'):
    x = Decimal(str(x_direita)) - _largura_texto_pdf(texto, tamanho)
    return _comando_texto_pdf(texto, max(x, Decimal('0.00')), y, tamanho, fonte, cor)


def _resumir_lancamentos_por_categoria(lancamentos):
    resumo = {}
    for lancamento in lancamentos:
        categoria = lancamento['categoria']
        valores = resumo.setdefault(categoria, {'debitos': Decimal('0.00'), 'creditos': Decimal('0.00'), 'quantidade': 0})
        valores['quantidade'] += 1
        if lancamento['tipo'] == 'debito':
            valores['debitos'] += lancamento['valor']
        else:
            valores['creditos'] += lancamento['valor']
    return sorted(resumo.items(), key=lambda item: item[0])


def _gerar_pdf_extrato_morador(contexto):
    largura_pagina = Decimal('842')
    altura_pagina = Decimal('595')
    margem = Decimal('32')
    comandos_paginas = []
    comandos = []
    pagina_atual = 1
    y = Decimal('0')
    mes_referencia = contexto['mes_referencia']
    titulo = f"Extrato pessoal do morador - {mes_referencia.strftime('%m/%Y')}"

    def adicionar_pagina():
        nonlocal comandos, y, pagina_atual
        if comandos:
            comandos.append(_comando_texto_pdf(f"Página {pagina_atual}", largura_pagina - margem - Decimal('55'), Decimal('18'), 8))
            comandos_paginas.append(comandos)
            pagina_atual += 1
        comandos = [
            '0.10 0.16 0.28 rg 0 552 842 43 re f',
            _comando_texto_pdf('RPF - Financeiro', margem, Decimal('575'), 10, 'F2', '1 1 1 rg'),
            _comando_texto_pdf(titulo, margem, Decimal('558'), 16, 'F2', '1 1 1 rg'),
            _comando_texto_direita_pdf(
                f"Gerado em {timezone.localtime().strftime('%d/%m/%Y às %H:%M')}",
                largura_pagina - margem,
                Decimal('575'),
                8,
                'F1',
                '1 1 1 rg',
            ),
        ]
        y = Decimal('530')

    def fechar_pdf():
        if comandos:
            comandos.append(_comando_texto_pdf(f"Página {pagina_atual}", largura_pagina - margem - Decimal('55'), Decimal('18'), 8))
            comandos_paginas.append(comandos)

    def garantir_espaco(altura_necessaria):
        if y - Decimal(str(altura_necessaria)) < Decimal('42'):
            adicionar_pagina()

    adicionar_pagina()

    # Cartões de resumo
    comandos.append('0.96 0.97 0.99 rg 32 454 778 68 re f')
    comandos.append('0.82 0.86 0.92 RG 32 454 778 68 re S')
    resumo = [
        ('Morador', contexto['morador_label']),
        ('Mês de referência', mes_referencia.strftime('%m/%Y')),
        ('Total de débitos', _formatar_moeda_pt_br(contexto['total_debitos'])),
        ('Créditos/descontos', _formatar_moeda_pt_br(contexto['total_creditos'])),
        ('Saldo a pagar', _formatar_moeda_pt_br(contexto['saldo_extrato'])),
    ]
    x_card = margem + Decimal('14')
    largura_card = Decimal('150')
    for label, valor in resumo:
        comandos.append(_comando_texto_pdf(label, x_card, Decimal('500'), 8))
        comandos.append(_comando_texto_pdf(valor, x_card, Decimal('480'), 11, 'F2'))
        x_card += largura_card
    y = Decimal('430')

    comandos.append(_comando_texto_pdf('Composição do extrato', margem, y, 12, 'F2'))
    y -= Decimal('28')

    def desenhar_item_composicao(item, x, y_topo, largura, altura=Decimal('42'), destaque=False):
        percentual = _formatar_percentual_pt_br(item['percentual'])
        fundo = '0.90 0.94 0.99 rg' if destaque else '0.95 0.97 0.99 rg'
        borda = '0.33 0.49 0.72 RG' if destaque else '0.82 0.86 0.92 RG'
        comandos.append(f'{fundo} {x:.2f} {y_topo - altura:.2f} {largura:.2f} {altura:.2f} re f')
        comandos.append(f'{borda} {x:.2f} {y_topo - altura:.2f} {largura:.2f} {altura:.2f} re S')
        comandos.append(_comando_texto_pdf(item['label'], x + Decimal('10'), y_topo - Decimal('13'), 7, 'F2'))
        comandos.append(_comando_texto_pdf(_formatar_moeda_pt_br(item['valor']), x + Decimal('10'), y_topo - Decimal('28'), 10, 'F2'))
        comandos.append(_comando_texto_direita_pdf(percentual, x + largura - Decimal('10'), y_topo - Decimal('28'), 7))

    item_parcelas = next((item for item in contexto['composicao'] if item['label'] == 'Parcelas do mês'), None)
    demais_itens = [item for item in contexto['composicao'] if item['label'] != 'Parcelas do mês']
    largura_total = largura_pagina - (margem * 2)
    if item_parcelas:
        desenhar_item_composicao(item_parcelas, margem, y, largura_total, Decimal('44'), destaque=True)
        y -= Decimal('56')

    espaco_coluna = Decimal('12')
    largura_item = (largura_total - (espaco_coluna * Decimal('3'))) / Decimal('4')
    for indice, item in enumerate(demais_itens):
        coluna = Decimal(str(indice % 4))
        linha = Decimal(str(indice // 4))
        x_comp = margem + (coluna * (largura_item + espaco_coluna))
        y_topo = y - (linha * Decimal('52'))
        desenhar_item_composicao(item, x_comp, y_topo, largura_item)
    linhas_demais = Decimal(str((len(demais_itens) + 3) // 4)) if demais_itens else Decimal('0')
    y -= (linhas_demais * Decimal('52')) + Decimal('12')

    comandos.append(_comando_texto_pdf('Detalhamento por categoria', margem, y, 12, 'F2'))
    y -= Decimal('18')
    comandos.append('0.12 0.18 0.30 rg 32 {:.2f} 778 20 re f'.format(y - Decimal('13')))
    for titulo_coluna, x in [('Categoria', Decimal('38')), ('Qtd.', Decimal('390')), ('Débitos', Decimal('470')), ('Créditos', Decimal('585')), ('Saldo', Decimal('700'))]:
        comandos.append(_comando_texto_pdf(titulo_coluna, x, y - Decimal('7'), 8, 'F2', '1 1 1 rg'))
    y -= Decimal('22')
    for indice, (categoria, valores) in enumerate(_resumir_lancamentos_por_categoria(contexto['lancamentos'])):
        saldo_categoria = valores['debitos'] - valores['creditos']
        cor_fundo = '1 1 1 rg' if indice % 2 == 0 else '0.97 0.98 0.99 rg'
        comandos.append(f'{cor_fundo} 32 {y - Decimal("13"):.2f} 778 19 re f')
        comandos.append(f'0.88 0.88 0.88 RG 32 {y - Decimal("13"):.2f} 778 19 re S')
        comandos.append(_comando_texto_pdf(categoria, Decimal('38'), y - Decimal('7'), 8))
        comandos.append(_comando_texto_pdf(str(valores['quantidade']), Decimal('398'), y - Decimal('7'), 8))
        comandos.append(_comando_texto_direita_pdf(_formatar_moeda_pt_br(valores['debitos']), Decimal('555'), y - Decimal('7'), 8))
        comandos.append(_comando_texto_direita_pdf(_formatar_moeda_pt_br(valores['creditos']), Decimal('675'), y - Decimal('7'), 8))
        comandos.append(_comando_texto_direita_pdf(_formatar_moeda_pt_br(saldo_categoria), Decimal('802'), y - Decimal('7'), 8, 'F2'))
        y -= Decimal('19')
    if not contexto['lancamentos']:
        comandos.append('0.99 0.99 0.99 rg 32 {:.2f} 778 19 re f'.format(y - Decimal('13')))
        comandos.append('0.88 0.88 0.88 RG 32 {:.2f} 778 19 re S'.format(y - Decimal('13')))
        comandos.append(_comando_texto_pdf('Nenhuma categoria com lançamento para este mês.', Decimal('38'), y - Decimal('7'), 8))
        y -= Decimal('19')

    y -= Decimal('10')
    comandos.append(_comando_texto_pdf('Critérios de leitura', margem, y, 11, 'F2'))
    y -= Decimal('14')
    criterios = [
        f"O extrato considera {len(contexto['lancamentos'])} lançamento(s) do mês de referência {mes_referencia.strftime('%m/%Y')}.",
        f"Saldo a pagar = débitos {_formatar_moeda_pt_br(contexto['total_debitos'])} menos créditos/descontos {_formatar_moeda_pt_br(contexto['total_creditos'])}.",
        'Cada linha abaixo mostra a data, a categoria, a descrição, o detalhe do cálculo e o valor separado entre débito e crédito.',
    ]
    for criterio in criterios:
        for linha in _quebrar_texto_pdf(criterio, 132):
            comandos.append(_comando_texto_pdf(linha, margem + Decimal('8'), y, 7))
            y -= Decimal('9')
    y -= Decimal('10')

    comandos.append(_comando_texto_pdf('Lançamentos', margem, y, 12, 'F2'))
    y -= Decimal('20')

    colunas = [
        ('Data', Decimal('32'), Decimal('58')),
        ('Categoria', Decimal('90'), Decimal('92')),
        ('Descrição e detalhe do cálculo', Decimal('182'), Decimal('410')),
        ('Débito', Decimal('592'), Decimal('105')),
        ('Crédito', Decimal('697'), Decimal('105')),
    ]

    def cabecalho_tabela():
        nonlocal y
        comandos.append('0.12 0.18 0.30 rg 32 {:.2f} 778 22 re f'.format(y - Decimal('15')))
        for titulo_coluna, x, largura in colunas:
            comandos.append(_comando_texto_pdf(titulo_coluna, x + Decimal('6'), y - Decimal('8'), 8, 'F2', '1 1 1 rg'))
        y -= Decimal('24')

    cabecalho_tabela()
    if not contexto['lancamentos']:
        garantir_espaco(28)
        comandos.append('0.99 0.99 0.99 rg 32 {:.2f} 778 24 re f'.format(y - Decimal('14')))
        comandos.append('0.86 0.86 0.86 RG 32 {:.2f} 778 24 re S'.format(y - Decimal('14')))
        comandos.append(_comando_texto_pdf('Nenhum lançamento encontrado para este mês.', margem + Decimal('6'), y - Decimal('7'), 8))
        y -= Decimal('28')
    else:
        for indice, lancamento in enumerate(contexto['lancamentos']):
            descricao = lancamento['descricao']
            detalhe = lancamento.get('detalhe') or '-'
            natureza = 'Débito' if lancamento['tipo'] == 'debito' else 'Crédito'
            linhas_descricao = _quebrar_texto_pdf(f"Descrição: {descricao} | Cálculo: {detalhe} | Natureza: {natureza}", 88)
            altura_linha = Decimal(str(max(30, 14 + (len(linhas_descricao) * 9))))
            if y - altura_linha - Decimal('8') < Decimal('42'):
                adicionar_pagina()
                comandos.append(_comando_texto_pdf('Lançamentos (continuação)', margem, y, 12, 'F2'))
                y -= Decimal('20')
                cabecalho_tabela()
            cor_fundo = '1 1 1 rg' if indice % 2 == 0 else '0.97 0.98 0.99 rg'
            comandos.append(f'{cor_fundo} 32 {y - altura_linha + Decimal("6"):.2f} 778 {altura_linha:.2f} re f')
            comandos.append(f'0.86 0.86 0.86 RG 32 {y - altura_linha + Decimal("6"):.2f} 778 {altura_linha:.2f} re S')
            for _, x, _ in colunas[1:]:
                y_base = y - altura_linha + Decimal('6')
                comandos.append(f'0.90 0.90 0.90 RG {x:.2f} {y_base:.2f} m {x:.2f} {y_base + altura_linha:.2f} l S')
            comandos.append(_comando_texto_pdf(lancamento['data'].strftime('%d/%m/%Y'), Decimal('38'), y - Decimal('8'), 8))
            comandos.append(_comando_texto_pdf(lancamento['categoria'], Decimal('96'), y - Decimal('8'), 8))
            y_texto = y - Decimal('8')
            for linha in linhas_descricao:
                comandos.append(_comando_texto_pdf(linha, Decimal('188'), y_texto, 7))
                y_texto -= Decimal('9')
            debito = _formatar_moeda_pt_br(lancamento['valor']) if lancamento['tipo'] == 'debito' else '-'
            credito = _formatar_moeda_pt_br(lancamento['valor']) if lancamento['tipo'] == 'credito' else '-'
            comandos.append(_comando_texto_direita_pdf(debito, Decimal('690'), y - Decimal('8'), 8))
            comandos.append(_comando_texto_direita_pdf(credito, Decimal('802'), y - Decimal('8'), 8))
            y -= altura_linha

    y -= Decimal('14')
    garantir_espaco(62)
    comandos.append('0.10 0.16 0.28 rg 485 {:.2f} 325 48 re f'.format(y - Decimal('40')))
    comandos.append(_comando_texto_pdf('Totais', Decimal('498'), y - Decimal('10'), 9, 'F2', '1 1 1 rg'))
    comandos.append(_comando_texto_pdf(f"Débitos: {_formatar_moeda_pt_br(contexto['total_debitos'])}", Decimal('575'), y - Decimal('10'), 8, 'F2', '1 1 1 rg'))
    comandos.append(_comando_texto_pdf(f"Créditos: {_formatar_moeda_pt_br(contexto['total_creditos'])}", Decimal('575'), y - Decimal('24'), 8, 'F2', '1 1 1 rg'))
    comandos.append(_comando_texto_pdf(f"Saldo a pagar: {_formatar_moeda_pt_br(contexto['saldo_extrato'])}", Decimal('575'), y - Decimal('38'), 9, 'F2', '1 1 1 rg'))

    fechar_pdf()

    objetos = [b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"]
    kids = []
    fonte_regular_obj = 3 + (len(comandos_paginas) * 2)
    fonte_bold_obj = fonte_regular_obj + 1
    for indice, comandos_pagina in enumerate(comandos_paginas):
        pagina_obj = 3 + (indice * 2)
        conteudo_obj = pagina_obj + 1
        kids.append(f"{pagina_obj} 0 R")
        stream = '\n'.join(comandos_pagina).encode('cp1252', errors='replace')
        objetos.append(
            f"{pagina_obj} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 {largura_pagina} {altura_pagina}] /Resources << /Font << /F1 {fonte_regular_obj} 0 R /F2 {fonte_bold_obj} 0 R >> >> /Contents {conteudo_obj} 0 R >> endobj\n".encode('latin-1')
        )
        objetos.append(
            f"{conteudo_obj} 0 obj << /Length {len(stream)} >> stream\n".encode('latin-1')
            + stream
            + b"\nendstream endobj\n"
        )
    objetos.insert(
        1,
        f"2 0 obj << /Type /Pages /Kids [{' '.join(kids)}] /Count {len(comandos_paginas)} >> endobj\n".encode('latin-1'),
    )
    objetos.append(f"{fonte_regular_obj} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> endobj\n".encode('latin-1'))
    objetos.append(f"{fonte_bold_obj} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >> endobj\n".encode('latin-1'))

    pdf = b'%PDF-1.4\n'
    offsets = [0]
    for obj in objetos:
        offsets.append(len(pdf))
        pdf += obj
    xref_start = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n".encode('latin-1') + b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode('latin-1')
    pdf += (f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF").encode('latin-1')
    return pdf



def _montar_pdf_por_comandos(comandos_paginas, largura_pagina, altura_pagina):
    objetos = [b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"]
    kids = []
    fonte_regular_obj = 3 + (len(comandos_paginas) * 2)
    fonte_bold_obj = fonte_regular_obj + 1
    for indice, comandos_pagina in enumerate(comandos_paginas):
        pagina_obj = 3 + (indice * 2)
        conteudo_obj = pagina_obj + 1
        kids.append(f"{pagina_obj} 0 R")
        stream = '\n'.join(comandos_pagina).encode('cp1252', errors='replace')
        objetos.append(
            f"{pagina_obj} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 {largura_pagina} {altura_pagina}] /Resources << /Font << /F1 {fonte_regular_obj} 0 R /F2 {fonte_bold_obj} 0 R >> >> /Contents {conteudo_obj} 0 R >> endobj\n".encode('latin-1')
        )
        objetos.append(
            f"{conteudo_obj} 0 obj << /Length {len(stream)} >> stream\n".encode('latin-1')
            + stream
            + b"\nendstream endobj\n"
        )
    objetos.insert(
        1,
        f"2 0 obj << /Type /Pages /Kids [{' '.join(kids)}] /Count {len(comandos_paginas)} >> endobj\n".encode('latin-1'),
    )
    objetos.append(f"{fonte_regular_obj} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> endobj\n".encode('latin-1'))
    objetos.append(f"{fonte_bold_obj} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >> endobj\n".encode('latin-1'))

    pdf = b'%PDF-1.4\n'
    offsets = [0]
    for obj in objetos:
        offsets.append(len(pdf))
        pdf += obj
    xref_start = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n".encode('latin-1') + b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode('latin-1')
    pdf += (f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF").encode('latin-1')
    return pdf


def _comandos_qrcode_pdf(payload_pix, x, y_topo, tamanho=Decimal('142')):
    if not payload_pix:
        return []
    qr = segno.make(payload_pix, error='m')
    matriz = list(qr.matrix)
    if not matriz:
        return []
    margem_modulos = Decimal('4')
    modulos = Decimal(str(len(matriz))) + (margem_modulos * Decimal('2'))
    modulo = Decimal(str(tamanho)) / modulos
    comandos = [f'1 1 1 rg {x:.2f} {y_topo - tamanho:.2f} {tamanho:.2f} {tamanho:.2f} re f', '0 0 0 rg']
    for linha_idx, linha in enumerate(matriz):
        for coluna_idx, escuro in enumerate(linha):
            if not escuro:
                continue
            x_modulo = Decimal(str(x)) + ((Decimal(str(coluna_idx)) + margem_modulos) * modulo)
            y_modulo = Decimal(str(y_topo)) - ((Decimal(str(linha_idx)) + margem_modulos + Decimal('1')) * modulo)
            comandos.append(f'{x_modulo:.2f} {y_modulo:.2f} {modulo:.2f} {modulo:.2f} re f')
    comandos.append(f'0.10 0.16 0.28 RG {x:.2f} {y_topo - tamanho:.2f} {tamanho:.2f} {tamanho:.2f} re S')
    return comandos


def _resolver_chave_pix_aluguel():
    config = ConfiguracaoFinanceira.objects.order_by('-atualizado_em', '-id').first()
    if not config:
        return ''
    return normalizar_chave_pix(config.conta_recebimentos_pix or config.conta_principal_pix or config.conta_pagamentos_pix or '')


def _gerar_ou_atualizar_cobranca_aluguel(contexto):
    morador = contexto['item']['morador']
    mes_referencia = contexto['mes_referencia']
    valor = (contexto['saldo_extrato'] or Decimal('0.00')).quantize(Decimal('0.01'))
    cobranca, criada = CobrancaAluguel.objects.get_or_create(
        morador=morador,
        mes_referencia=mes_referencia,
        defaults={'valor': valor},
    )
    deve_recriar = criada or cobranca.status != 'pago' or cobranca.valor != valor or not cobranca.payload_pix
    if deve_recriar:
        cobranca.valor = valor
        if not cobranca.txid or len(cobranca.txid) > 25:
            cobranca.save()
            cobranca.txid = f"RPFAL{cobranca.id:020d}"
        resultado = criar_cobranca_pix_avulsa(
            txid=cobranca.txid,
            valor=valor,
            chave_pix=_resolver_chave_pix_aluguel(),
            nome_pagador=contexto['morador_label'],
            categoria='Aluguel',
        )
        cobranca.txid = resultado.get('txid') or cobranca.txid
        cobranca.payload_pix = resultado.get('payload_pix') or cobranca.payload_pix
        cobranca.status_gateway = resultado.get('status_gateway') or cobranca.status_gateway
        cobranca.provider_payload = resultado.get('provider_payload') or {}
        cobranca.status = 'aguardando_pagamento' if cobranca.status != 'pago' else cobranca.status
        cobranca.save()
    return cobranca


def _gerar_pdf_boleto_aluguel(contexto, cobranca):
    largura_pagina = Decimal('595')
    altura_pagina = Decimal('842')
    margem = Decimal('36')
    y = Decimal('0')
    valor = _formatar_moeda_pt_br(cobranca.valor)
    vencimento = contexto['mes_referencia'].replace(day=10)
    chave_pix = _resolver_chave_pix_aluguel()
    payload = cobranca.payload_pix or 'PIX indisponível: configure a chave PIX de recebimentos.'
    comandos = [
        '1 1 1 rg 0 0 595 842 re f',
        '0.10 0.16 0.28 rg 0 778 595 64 re f',
        _comando_texto_pdf('Associação Cultural República Portão dos Fundos', margem, Decimal('815'), 10, 'F2', '1 1 1 rg'),
        _comando_texto_pdf('Boleto PIX - Cobrança de Aluguel', margem, Decimal('792'), 18, 'F2', '1 1 1 rg'),
        _comando_texto_direita_pdf(f'Emitido em {timezone.localtime().strftime("%d/%m/%Y às %H:%M")}', largura_pagina - margem, Decimal('815'), 8, 'F1', '1 1 1 rg'),
    ]
    comandos.append('0.96 0.98 1 rg 36 682 523 72 re f')
    comandos.append('0.72 0.80 0.92 RG 36 682 523 72 re S')
    resumo = [
        ('Morador', contexto['morador_label']),
        ('Referência', contexto['mes_referencia'].strftime('%m/%Y')),
        ('Classificação', 'Aluguel'),
        ('Valor', valor),
    ]
    x = margem + Decimal('14')
    for label, conteudo in resumo:
        comandos.append(_comando_texto_pdf(label, x, Decimal('730'), 8, 'F2'))
        comandos.append(_comando_texto_pdf(conteudo, x, Decimal('708'), 11, 'F2'))
        x += Decimal('126')

    comandos.append(_comando_texto_pdf('Beneficiário', margem, Decimal('650'), 9, 'F2'))
    comandos.append(_comando_texto_pdf('Associação Cultural República Portão dos Fundos', margem, Decimal('632'), 11, 'F2'))
    comandos.append(_comando_texto_pdf('Tipo de cobrança: Aluguel', margem, Decimal('615'), 9))
    comandos.append(_comando_texto_pdf(f'Chave PIX: {chave_pix or "não configurada"}', margem, Decimal('598'), 9))
    comandos.append(_comando_texto_pdf(f'TXID: {cobranca.txid}', margem, Decimal('581'), 8))
    comandos.append(_comando_texto_pdf(f'Vencimento: {vencimento.strftime("%d/%m/%Y")}', margem, Decimal('564'), 9))

    comandos.append('0.10 0.16 0.28 rg 36 540 523 30 re f')
    comandos.append(_comando_texto_pdf('Pagamento via PIX', Decimal('50'), Decimal('552'), 12, 'F2', '1 1 1 rg'))
    comandos.append('0.98 0.98 0.98 rg 36 308 523 232 re f')
    comandos.append('0.82 0.86 0.92 RG 36 308 523 232 re S')
    comandos.extend(_comandos_qrcode_pdf(cobranca.payload_pix, Decimal('56'), Decimal('514'), Decimal('150')))
    comandos.append(_comando_texto_pdf('Aponte a câmera do banco para o QR Code', Decimal('230'), Decimal('500'), 11, 'F2'))
    comandos.append(_comando_texto_pdf('ou use o PIX copia e cola abaixo.', Decimal('230'), Decimal('482'), 9))
    comandos.append(_comando_texto_pdf(f'Valor a pagar: {valor}', Decimal('230'), Decimal('455'), 13, 'F2'))

    comandos.append(_comando_texto_pdf('PIX copia e cola', margem, Decimal('278'), 10, 'F2'))
    comandos.append('0.95 0.97 0.99 rg 36 122 523 142 re f')
    comandos.append('0.82 0.86 0.92 RG 36 122 523 142 re S')
    y = Decimal('246')
    for linha in _quebrar_texto_pdf(payload, 86)[:12]:
        comandos.append(_comando_texto_pdf(linha, Decimal('48'), y, 7))
        y -= Decimal('10')

    comandos.append('0.10 0.16 0.28 rg 36 64 523 34 re f')
    comandos.append(_comando_texto_pdf('Documento gerado pelo ERP RPF. Confirme recebedor, valor e TXID antes de pagar.', Decimal('48'), Decimal('77'), 8, 'F2', '1 1 1 rg'))
    return _montar_pdf_por_comandos([comandos], largura_pagina, altura_pagina)


def _contexto_extrato_morador(request, morador_id):
    if not _usuario_pode_ver_extrato_morador(request, morador_id):
        raise PermissionDenied('Você só pode acessar o seu próprio extrato individual.')

    mes_referencia = resolver_mes_referencia(request.GET.get('mes'))
    resumo = calcular_rateio_financeiro(mes_referencia, incluir_pendencia=True)
    item = next((i for i in resumo['rateio_moradores'] if i['morador'].id == morador_id), None)
    if item is None:
        raise PermissionDenied('Morador não encontrado no rateio do mês.')

    morador_label = item['morador'].apelido or item['morador'].nome
    total = item['valor'] or Decimal('0.00')
    composicao = []
    for label, valor in [
        ('Aluguel', item['aluguel']),
        ('Contas fixas', item['fixas']),
        ('Caixinha/consumo', item['caixinha']),
        ('Parcelas do mês', item['parcelas']),
        ('Extras', item['extra']),
    ]:
        composicao.append({'label': label, 'valor': valor, 'percentual': _valor_percentual(valor, total)})

    lancamentos, total_debitos, total_creditos, saldo_extrato = _montar_extrato_morador(resumo, item, mes_referencia)
    return {
        'mes_referencia': mes_referencia,
        'mes_anterior': (mes_referencia - timedelta(days=1)).replace(day=1),
        'mes_proximo': (mes_referencia + timedelta(days=32)).replace(day=1),
        'item': item,
        'morador_label': morador_label,
        'composicao': composicao,
        'lancamentos': lancamentos,
        'total_debitos': total_debitos,
        'total_creditos': total_creditos,
        'saldo_extrato': saldo_extrato,
    }


@login_required
def financeiro_prestacao_contas(request):
    mes_referencia = resolver_mes_referencia(request.GET.get('mes'))
    morador_logado = get_user_morador(request.user)
    if not _usuario_pode_ver_prestacao_geral(request):
        if morador_logado:
            return redirect(
                f"{redirect('financeiro_prestacao_contas_morador', morador_id=morador_logado.id).url}"
                f"?mes={mes_referencia.strftime('%Y-%m')}"
            )
        raise PermissionDenied('Você não tem permissão para acessar a prestação de contas.')

    resumo = calcular_rateio_financeiro(mes_referencia, incluir_pendencia=True)
    resumo['rateio_moradores'] = sorted(
        resumo['rateio_moradores'],
        key=lambda item: (item['morador'].ordem_hierarquia, item['morador'].nome),
    )
    total_rateio = resumo['total_rateio']

    composicao_raw = [
        ('Aluguel', resumo['valor_aluguel']),
        ('Contas fixas', resumo['valor_fixas_total']),
        ('Parcelas do mês', resumo['total_parcelas_mes_rateio']),
        ('Extras', resumo['pendencia_total_mes']),
        ('Descontos', resumo['desconto_total_mes']),
    ]
    composicao_gastos = []
    for label, valor in composicao_raw:
        composicao_gastos.append({
            'label': label,
            'valor': valor,
            'percentual': _valor_percentual(valor, total_rateio),
        })

    parcelas_ordenadas = sorted(resumo['parcelas_rateio'], key=lambda p: p.nota.data_emissao or mes_referencia)
    calendario = {}
    for parcela in parcelas_ordenadas:
        data_ref = parcela.nota.data_emissao or mes_referencia
        if data_ref.month != mes_referencia.month or data_ref.year != mes_referencia.year:
            continue
        bucket = calendario.setdefault(data_ref, {'data': data_ref, 'total': Decimal('0.00'), 'qtd': 0})
        bucket['total'] += parcela.valor or Decimal('0.00')
        bucket['qtd'] += 1

    return render(request, 'core/financeiro_prestacao_contas.html', {
        'mes_referencia': mes_referencia,
        'mes_anterior': (mes_referencia - timedelta(days=1)).replace(day=1),
        'mes_proximo': (mes_referencia + timedelta(days=32)).replace(day=1),
        'composicao_gastos': composicao_gastos,
        'calendario_gastos': sorted(calendario.values(), key=lambda x: x['data']),
        **resumo,
    })


@login_required
def financeiro_prestacao_contas_morador(request, morador_id):
    contexto = _contexto_extrato_morador(request, morador_id)
    return render(request, 'core/financeiro_prestacao_contas_detalhe.html', contexto)


@login_required
def exportar_boleto_aluguel_morador_pdf(request, morador_id):
    contexto = _contexto_extrato_morador(request, morador_id)
    cobranca = _gerar_ou_atualizar_cobranca_aluguel(contexto)
    mes_referencia = contexto['mes_referencia']
    pdf = _gerar_pdf_boleto_aluguel(contexto, cobranca)
    nome_morador = slugify(contexto['morador_label']) or f"morador-{morador_id}"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="boleto_aluguel_{nome_morador}_{mes_referencia.strftime("%Y_%m")}.pdf"'
    )
    return response


@login_required
def exportar_extrato_morador_pdf(request, morador_id):
    contexto = _contexto_extrato_morador(request, morador_id)
    mes_referencia = contexto['mes_referencia']
    pdf = _gerar_pdf_extrato_morador(contexto)
    nome_morador = slugify(contexto['morador_label']) or f"morador-{morador_id}"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="extrato_pessoal_{nome_morador}_{mes_referencia.strftime("%Y_%m")}.pdf"'
    )
    return response


@setor_required(group_name='Financeiro', morador_view_attr='acesso_financeiro_visualizar', morador_edit_attr='acesso_financeiro_editar')
def financeiro(request):
    can_edit_financeiro = can_edit(request, 'acesso_financeiro_editar')
    configuracao = ConfiguracaoFinanceira.objects.order_by('-id').first()
    configuracao_form = None
    if request.method == 'POST':
        if 'delete_ajuste_id' in request.POST:
            mes = datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)
            AjusteMorador.objects.filter(id=request.POST.get('delete_ajuste_id'), mes_referencia=mes).delete()
            return redirect(f"{redirect('financeiro_aluguel').url}?mes={mes.strftime('%Y-%m')}")
        if 'desconto_submit' in request.POST:
            mes = datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)
            form = DescontoMensalForm(request.POST)
            if form.is_valid():
                from core.models import DescontoMensal
                DescontoMensal.objects.update_or_create(mes_referencia=mes, defaults={'valor_total': form.cleaned_data['valor_total']})
                return redirect(f"{redirect('financeiro_aluguel').url}?mes={mes.strftime('%Y-%m')}")
        elif 'ajuste_submit' in request.POST:
            fs = AjusteMoradorFormSet(
                request.POST,
                queryset=AjusteMorador.objects.filter(mes_referencia=datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)),
                prefix='ajuste',
            )
            if fs.is_valid():
                mes = datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)
                for ajuste in fs.save(commit=False):
                    ajuste.mes_referencia = mes
                    ajuste.save()
                for obj in fs.deleted_objects:
                    obj.delete()
                return redirect(f"{redirect('financeiro_aluguel').url}?mes={mes.strftime('%Y-%m')}")
        elif 'pendencia_submit' in request.POST:
            mes = datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)
            fs = PendenciaMensalItemFormSet(
                request.POST,
                queryset=PendenciaMensalItem.objects.filter(mes_referencia=mes),
                prefix='pendencia',
            )
            if fs.is_valid():
                itens = fs.save(commit=False)
                for item in itens:
                    item.mes_referencia = mes
                    item.save()
                for obj in fs.deleted_objects:
                    obj.delete()
                return redirect(f"{redirect('financeiro_aluguel').url}?mes={mes.strftime('%Y-%m')}")
        elif 'contas_casa_submit' in request.POST:
            mes = datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)
            fs = ContaCasaFormSet(
                request.POST,
                queryset=ContaCasa.objects.all().order_by('data_vencimento', 'nome', 'id'),
                prefix='contas_casa',
            )
            if fs.is_valid():
                contas = fs.save(commit=False)
                for conta in contas:
                    conta.mes_referencia = mes
                    conta.save()
                for obj in fs.deleted_objects:
                    obj.delete()
                return redirect(f"{redirect('financeiro_aluguel').url}?mes={mes.strftime('%Y-%m')}")
        else:
            configuracao_form = ConfiguracaoFinanceiraForm(request.POST, instance=configuracao)
            if configuracao_form.is_valid():
                configuracao_form.save()
                return redirect('financeiro_aluguel')
    if configuracao_form is None:
        configuracao_form = ConfiguracaoFinanceiraForm(instance=configuracao)

    mes_referencia = resolver_mes_referencia(request.GET.get('mes'))
    resumo = calcular_rateio_financeiro(mes_referencia, incluir_pendencia=True)
    comprovantes_map = {
        item.morador_id: item
        for item in ComprovantePagamentoMorador.objects.filter(
            mes_referencia=mes_referencia,
            morador__in=resumo['moradores_ativos'],
        ).select_related('morador')
    }
    for item in resumo['rateio_moradores']:
        item['comprovante'] = comprovantes_map.get(item['morador'].id)
        divida_morador = item['valor'] if item['valor'] is not None else Decimal('0.00')
        item['status_pagamento'] = 'pago' if item['comprovante'] or divida_morador <= Decimal('1.00') else 'pendente'

    total_recebido = Mensalidade.objects.filter(pago=True).aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    total_a_arrecadar = sum((item['valor'] for item in resumo['rateio_moradores']), Decimal('0.00')).quantize(Decimal('0.01'))
    total_expr = ExpressionWrapper(
        Case(
            When(nota__quantidade__gt=0, then=F('nota__quantidade') * F('nota__valor')),
            default=F('nota__valor'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    parcelas_notas = NotaParcela.objects.filter(
        mes_referencia=mes_referencia,
        nota__setor='compras',
    ).select_related('nota').annotate(total_valor=total_expr).order_by('-vencimento', '-id')
    return render(request, 'core/financeiro.html', {
        'total_recebido': total_recebido,
        'total_a_arrecadar': total_a_arrecadar,
        'notas': parcelas_notas,
        'configuracao_form': configuracao_form,
        'parcelas_abertas': resumo['parcelas_rateio'].filter(status='pendente').order_by('vencimento', 'id'),
        'mes_referencia': mes_referencia,
        'mes_anterior': (mes_referencia - timedelta(days=1)).replace(day=1),
        'mes_proximo': (mes_referencia + timedelta(days=32)).replace(day=1),
        'desconto_form': DescontoMensalForm(),
        'pendencia_formset': PendenciaMensalItemFormSet(
            queryset=PendenciaMensalItem.objects.filter(mes_referencia=mes_referencia).order_by('id'),
            prefix='pendencia',
        ),
        'ajuste_formset': AjusteMoradorFormSet(
            queryset=AjusteMorador.objects.filter(mes_referencia=mes_referencia).order_by('id'),
            prefix='ajuste',
        ),
        'contas_casa_formset': ContaCasaFormSet(
            queryset=ContaCasa.objects.all().order_by('data_vencimento', 'nome', 'id'),
            prefix='contas_casa',
        ),
        'rateio_colspan': 9 + len(resumo['contas_fixas']),
        'can_edit_financeiro': can_edit_financeiro,
        **resumo,
    })


@setor_required(group_name='Financeiro', morador_view_attr='acesso_financeiro_visualizar', morador_edit_attr='acesso_financeiro_editar')
def financeiro_registros_mensais(request):
    registros = RegistroFinanceiroMensal.objects.select_related('salvo_por').prefetch_related('moradores')
    mes_referencia = resolver_mes_referencia(request.GET.get('mes')) if request.GET.get('mes') else None
    registro_selecionado = None
    if mes_referencia:
        registro_selecionado = registros.filter(mes_referencia=mes_referencia).first()
    if registro_selecionado is None:
        registro_selecionado = registros.first()

    return render(request, 'core/financeiro_registros_mensais.html', {
        'registros': registros,
        'registro_selecionado': registro_selecionado,
        'moradores_registro': registro_selecionado.moradores.all() if registro_selecionado else [],
        'can_edit_financeiro': can_edit(request, 'acesso_financeiro_editar'),
    })


@require_POST
@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def salvar_registro_financeiro(request):
    mes_referencia = resolver_mes_referencia(request.POST.get('mes'))
    salvar_registro_financeiro_mensal(mes_referencia, request.user)
    messages.success(request, f'Registro financeiro de {mes_referencia.strftime("%m/%Y")} salvo com sucesso.')
    next_url = request.POST.get('next')
    if next_url == 'registros':
        return redirect(f"{redirect('financeiro_registros_mensais').url}?mes={mes_referencia.strftime('%Y-%m')}")
    return redirect(f"{redirect('financeiro_aluguel').url}?mes={mes_referencia.strftime('%Y-%m')}")


@setor_required(group_name='Financeiro', morador_view_attr='acesso_financeiro_visualizar', morador_edit_attr='acesso_financeiro_editar')
def exportar_financeiro_csv(request):
    mes_referencia = resolver_mes_referencia(request.GET.get('mes'))
    resumo = calcular_rateio_financeiro(mes_referencia, incluir_pendencia=False)
    total_recebido = Mensalidade.objects.filter(pago=True).aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="financeiro_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Resumo Financeiro'])
    writer.writerow(['Mes de Referencia', mes_referencia.strftime('%m/%Y')])
    writer.writerow(['Total Recebido', total_recebido])
    writer.writerow(['Despesas Pagas', resumo['total_despesas']])
    return response


@require_POST
@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def pagar_nota(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id)
    if nota.status != 'pago':
        nota.status = 'pago'
        nota.data_pagamento = timezone.now().date()
        nota.save(update_fields=['status', 'data_pagamento'])
    return redirect('financeiro_aluguel')


@require_POST
@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def pagar_parcela(request, parcela_id):
    parcela = get_object_or_404(NotaParcela, id=parcela_id)
    if parcela.status != 'pago':
        parcela.status = 'pago'
        parcela.save(update_fields=['status'])
    return redirect('financeiro_aluguel')


@login_required
@require_POST
def anexar_comprovante_pagamento(request, morador_id):
    morador_logado = get_user_morador(request.user)
    can_edit_financeiro = can_edit(request, 'acesso_financeiro_editar')
    if not can_edit_financeiro and (not morador_logado or morador_logado.id != morador_id):
        raise PermissionDenied('Você não pode anexar comprovante para este morador.')

    morador = get_object_or_404(Morador, id=morador_id, ativo=True)
    arquivo = request.FILES.get('comprovante')
    mes_param = request.POST.get('mes')
    next_view = request.POST.get('next', 'financeiro_aluguel')

    if not arquivo or not mes_param:
        return redirect(next_view if next_view in ('financeiro', 'financeiro_aluguel', 'perfil') else 'financeiro_aluguel')

    mes_referencia = resolver_mes_referencia(mes_param)
    ComprovantePagamentoMorador.objects.update_or_create(
        morador=morador,
        mes_referencia=mes_referencia,
        defaults={'arquivo': arquivo},
    )
    if next_view == 'perfil':
        return redirect('perfil')
    return redirect(f"{redirect('financeiro_aluguel').url}?mes={mes_referencia.strftime('%Y-%m')}")


@login_required
def ver_comprovante_pagamento(request, comprovante_id):
    comprovante = get_object_or_404(ComprovantePagamentoMorador.objects.select_related('morador'), id=comprovante_id)
    morador_logado = get_user_morador(request.user)
    can_view_financeiro = can_edit(request, 'acesso_financeiro_visualizar') or can_edit(request, 'acesso_financeiro_editar')

    if not can_view_financeiro and (not morador_logado or morador_logado.id != comprovante.morador_id):
        raise PermissionDenied('Você não pode visualizar este comprovante.')

    destino = 'perfil' if (morador_logado and morador_logado.id == comprovante.morador_id and not can_view_financeiro) else 'financeiro_aluguel'
    if destino == 'financeiro':
        destino = f"{redirect('financeiro_aluguel').url}?mes={comprovante.mes_referencia.strftime('%Y-%m')}"

    if not comprovante.arquivo or not comprovante.arquivo.name:
        messages.error(request, 'Comprovante não encontrado para este registro.')
        return redirect(destino)

    if not comprovante.arquivo.storage.exists(comprovante.arquivo.name):
        messages.error(request, 'Arquivo do comprovante não está mais disponível.')
        return redirect(destino)

    try:
        arquivo = comprovante.arquivo.open('rb')
    except (FileNotFoundError, OSError):
        messages.error(request, 'Não foi possível abrir o arquivo do comprovante.')
        return redirect(destino)

    return FileResponse(
        arquivo,
        as_attachment=False,
        filename=comprovante.arquivo.name.split('/')[-1],
    )


@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def editar_parcela(request, parcela_id):
    parcela = get_object_or_404(NotaParcela, id=parcela_id)
    form = ParcelaForm(request.POST or None, instance=parcela)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('financeiro_aluguel')
    return render(request, 'core/editar_parcela.html', {'form': form, 'parcela': parcela})


@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def editar_rateio_parcela(request, parcela_id):
    parcela = get_object_or_404(NotaParcela.objects.select_related('nota'), id=parcela_id)
    moradores_ativos = list(Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome'))
    if request.method == 'POST':
        selecionados = {int(mid) for mid in request.POST.getlist('moradores_rateio') if mid.isdigit()}
        ativos_ids = {morador.id for morador in moradores_ativos}
        if not selecionados:
            selecionados = set(ativos_ids)
        excluidos = ativos_ids - selecionados
        ParcelaRateioExclusao.objects.filter(parcela=parcela).exclude(morador_id__in=excluidos).delete()
        existentes = set(ParcelaRateioExclusao.objects.filter(parcela=parcela).values_list('morador_id', flat=True))
        for morador_id in excluidos - existentes:
            ParcelaRateioExclusao.objects.create(parcela=parcela, morador_id=morador_id)
        mes_param = request.POST.get('mes_param')
        return redirect(f"{redirect('financeiro_aluguel').url}?mes={mes_param}") if mes_param else redirect('financeiro_aluguel')

    excluidos_ids = set(ParcelaRateioExclusao.objects.filter(parcela=parcela).values_list('morador_id', flat=True))
    moradores_contexto = [{'morador': morador, 'selecionado': morador.id not in excluidos_ids} for morador in moradores_ativos]
    return render(request, 'core/editar_rateio_parcela.html', {
        'parcela': parcela,
        'moradores_contexto': moradores_contexto,
    })


def _primeiro_vencimento(data_emissao):
    mes = (data_emissao.replace(day=1) + timedelta(days=32)).replace(day=1) if data_emissao.day >= 5 else data_emissao.replace(day=1)
    return mes.replace(day=5), mes


def criar_parcelas_nota(nota):
    if nota.parcelas.exists():
        return
    quantidade = nota.quantidade_parcelas or 1
    quantidade_itens = nota.quantidade or 0
    total = (nota.valor or Decimal('0.00')) * quantidade_itens if quantidade_itens > 0 else (nota.valor or Decimal('0.00'))
    vencimento, mes_ref = _primeiro_vencimento(nota.data_emissao)
    valor_parcela = (total / quantidade).quantize(Decimal('0.01')) if quantidade else total
    restante = total
    for idx in range(1, quantidade + 1):
        valor = valor_parcela if idx < quantidade else restante.quantize(Decimal('0.01'))
        NotaParcela.objects.create(nota=nota, numero=idx, valor=valor, vencimento=vencimento, mes_referencia=mes_ref, status='pendente')
        restante -= valor
        mes_ref = (mes_ref + timedelta(days=32)).replace(day=1)
        vencimento = mes_ref.replace(day=5)


@setor_required(group_name='Compras', morador_view_attr='acesso_compras_visualizar', morador_edit_attr='acesso_compras_editar')
def compras(request):
    can_edit_compras = can_edit(request, 'acesso_compras_editar')
    garantir_setores_e_locais_base()
    form = NotaFiscalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        nota = form.save(commit=False)
        nota.setor = 'compras'
        if not nota.parcelado:
            nota.quantidade_parcelas = 1
        nota.save()
        if nota.adicionar_estoque and nota.quantidade > 0 and nota.setor_estoque and nota.local_estoque:
            produto, criado = Produto.objects.get_or_create(nome=nota.descricao, setor=nota.setor_estoque, local=nota.local_estoque, defaults={'descricao': nota.tipo_item or '', 'quantidade': nota.quantidade, 'estoque_minimo': 0})
            if not criado:
                produto.quantidade += nota.quantidade
                if nota.tipo_item and produto.descricao != nota.tipo_item:
                    produto.descricao = nota.tipo_item
                produto.save(update_fields=['quantidade', 'descricao'])
        criar_parcelas_nota(nota)
        return redirect('compras')
    mes_cobranca_sub = NotaParcela.objects.filter(nota_id=OuterRef('pk')).order_by('mes_referencia').values('mes_referencia')[:1]
    total_valor_expr = Case(
        When(quantidade__gt=0, then=F('quantidade') * F('valor')),
        default=F('valor'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    notas_base = NotaFiscal.objects.filter(setor='compras').annotate(
        total_valor=ExpressionWrapper(total_valor_expr, output_field=DecimalField(max_digits=12, decimal_places=2)),
        mes_cobranca=Subquery(mes_cobranca_sub),
    )
    mes_referencia = resolver_mes_referencia(request.GET.get('mes'))
    notas = notas_base.filter(mes_cobranca=mes_referencia).order_by('-data_emissao', '-id')

    meses_disponiveis = list(
        notas_base.exclude(mes_cobranca__isnull=True)
        .values_list('mes_cobranca', flat=True)
        .distinct()
        .order_by('-mes_cobranca')
    )

    return render(request, 'core/compras.html', {
        'form': form,
        'notas': notas,
        'can_edit_compras': can_edit_compras,
        'mes_referencia': mes_referencia,
        'mes_anterior': (mes_referencia - timedelta(days=1)).replace(day=1),
        'mes_proximo': (mes_referencia + timedelta(days=32)).replace(day=1),
        'meses_disponiveis': meses_disponiveis,
        'comodos': Comodo.objects.select_related('andar').order_by('andar__nome', 'nome'),
        'locais': LocalArmazenamento.objects.select_related('comodo').order_by('nome'),
    })


@setor_required(group_name='Compras', morador_view_attr='acesso_compras_visualizar')
def exportar_compras_csv(request):
    total_valor_expr = Case(
        When(quantidade__gt=0, then=F('quantidade') * F('valor')),
        default=F('valor'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    notas = NotaFiscal.objects.filter(setor='compras').annotate(
        total_valor=ExpressionWrapper(total_valor_expr, output_field=DecimalField(max_digits=12, decimal_places=2))
    ).order_by('-data_emissao', '-id')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="compras_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Notas de Compras'])
    for nota in notas:
        writer.writerow([nota.descricao, nota.fornecedor, nota.valor, nota.total_valor])
    return response


@setor_required(group_name='Compras', morador_edit_attr='acesso_compras_editar')
def editar_nota_compra(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id, setor='compras')
    if request.method == 'POST' and 'excluir_submit' in request.POST:
        nota.delete()
        return redirect('compras')
    form = NotaFiscalForm(request.POST or None, instance=nota)
    if request.method == 'POST' and form.is_valid():
        nota = form.save(commit=False)
        nota.setor = 'compras'
        nota.save()
        messages.success(request, 'Nota atualizada com sucesso.')
        return redirect('compras')
    return render(request, 'core/editar_nota.html', {'form': form, 'nota': nota, 'comodos': Comodo.objects.select_related('andar').order_by('andar__nome', 'nome'), 'locais': LocalArmazenamento.objects.select_related('comodo').order_by('nome')})
