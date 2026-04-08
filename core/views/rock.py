import logging
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Case, DecimalField, ExpressionWrapper, F, Sum, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

from core.forms import CompraIngressoRockForm, IngressoRockForm, LoteIngressoRockForm, RockEventoForm, RockItemForm
from django.forms import inlineformset_factory
from core.models import ConfiguracaoFinanceira, ConsumoEstoque, IngressoRock, LoteIngressoRock, NotaFiscal, PedidoIngressoRock, RockEvento, RockItem
from core.services.estoque import obter_morador_casa, remover_consumo_e_devolver_estoque, sincronizar_consumo_item
from core.services.pix_gateway import criar_cobranca_pix
from core.services.rock import criar_ingresso_rock, remover_ingresso_rock

from .common import can_edit, get_user_morador, setor_required

logger = logging.getLogger('core.views.rock')
RockItemFormSet = inlineformset_factory(RockEvento, RockItem, form=RockItemForm, extra=1, can_delete=True)


def _texto_pdf(valor):
    return str(valor).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _gerar_pdf_simples(titulo, linhas):
    conteudo = [f"BT /F1 12 Tf 40 800 Td ({_texto_pdf(titulo)}) Tj"]
    y = 780
    for linha in linhas:
        conteudo.append(f"1 0 0 1 40 {y} Tm ({_texto_pdf(linha)}) Tj")
        y -= 16
        if y < 40:
            break
    conteudo.append('ET')
    stream = '\n'.join(conteudo).encode('latin-1', errors='replace')
    objetos = [b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n", b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n", b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n", b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n", f"5 0 obj << /Length {len(stream)} >> stream\n".encode('latin-1') + stream + b"\nendstream endobj\n"]
    pdf = b'%PDF-1.4\n'
    offsets = [0]
    for obj in objetos:
        offsets.append(len(pdf)); pdf += obj
    xref_start = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n".encode('latin-1') + b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode('latin-1')
    pdf += (f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF").encode('latin-1')
    return pdf


def _sync_consumo_rock(item, data_consumo):
    if not item.produto_id:
        return
    consumo, created = sincronizar_consumo_item(
        consumo_atual=getattr(item, 'consumo', None),
        produto_id=item.produto_id,
        quantidade=item.quantidade,
        morador=obter_morador_casa(),
        data=data_consumo,
        setor='rock',
        rock_evento=item.rock_evento,
    )
    if created:
        item.consumo = consumo
        item.save(update_fields=['consumo'])


@setor_required(group_name='Rock', morador_view_attr='acesso_rock_visualizar', morador_edit_attr='acesso_rock_editar')
def rock(request):
    can_edit_rock = can_edit(request, 'acesso_rock_editar')
    evento_form = RockEventoForm(request.POST or None)
    itens_formset = RockItemFormSet(request.POST or None)
    if request.method == 'POST' and evento_form.is_valid() and itens_formset.is_valid():
        evento = evento_form.save()
        itens_formset.instance = evento
        for item in itens_formset.deleted_objects:
            remover_consumo_e_devolver_estoque(getattr(item, 'consumo', None)); item.delete()
        for item in itens_formset.save(commit=False):
            item.rock_evento = evento
            item.save()
            _sync_consumo_rock(item, evento.data)
        return redirect('rock')

    eventos = RockEvento.objects.prefetch_related('itens', 'lotes').order_by('-data')
    consumos_rock = ConsumoEstoque.objects.filter(setor='rock', rock_evento__isnull=False).select_related('rock_evento', 'produto').order_by('-data', '-id')
    total_expr = ExpressionWrapper(Case(When(quantidade__gt=0, then=F('quantidade') * F('valor')), default=F('valor'), output_field=DecimalField(max_digits=12, decimal_places=2)), output_field=DecimalField(max_digits=12, decimal_places=2))
    total_por_rock = {i['rock_evento_id']: i['total'] for i in NotaFiscal.objects.filter(setor='compras', categoria_compra='rock', rock_evento__isnull=False, tipo_item='Bem de Troca').annotate(total_valor=total_expr).values('rock_evento_id').annotate(total=Sum('total_valor'))}
    total_gasto = Decimal('0.00')
    for evento in eventos:
        evento.total_gasto = total_por_rock.get(evento.id) or Decimal('0.00')
        evento.lotes_resumo = list(evento.lotes.all())
        total_gasto += evento.total_gasto
    return render(request, 'core/rock.html', {'evento_form': evento_form, 'itens_formset': itens_formset, 'eventos': eventos, 'consumos_rock': consumos_rock, 'can_edit_rock': can_edit_rock, 'total_gasto': total_gasto})


@setor_required(group_name='Rock', morador_edit_attr='acesso_rock_editar')
def editar_rock(request, evento_id):
    evento = get_object_or_404(RockEvento, id=evento_id)
    if request.method == 'POST' and 'excluir_submit' in request.POST:
        evento.delete()
        return redirect('rock')
    evento_form = RockEventoForm(request.POST or None, instance=evento)
    itens_formset = RockItemFormSet(request.POST or None, instance=evento)
    if request.method == 'POST' and evento_form.is_valid() and itens_formset.is_valid():
        evento = evento_form.save()
        for item in itens_formset.deleted_objects:
            remover_consumo_e_devolver_estoque(getattr(item, 'consumo', None)); item.delete()
        for item in itens_formset.save(commit=False):
            item.rock_evento = evento
            item.save()
            _sync_consumo_rock(item, evento.data)
        return redirect('rock')
    return render(request, 'core/editar_rock.html', {'evento_form': evento_form, 'itens_formset': itens_formset, 'evento': evento})


@setor_required(group_name='Rock', morador_view_attr='acesso_rock_visualizar', morador_edit_attr='acesso_rock_editar')
def ingressos_rock(request, evento_id):
    evento = get_object_or_404(RockEvento, id=evento_id)
    can_edit_rock = can_edit(request, 'acesso_rock_editar')
    ingressos = IngressoRock.objects.filter(rock_evento=evento).order_by('nome')
    form = IngressoRockForm(request.POST or None, evento=evento)
    if request.method == 'POST':
        if not can_edit_rock:
            raise PermissionDenied('Voce nao tem permissao para editar ingressos.')
        if 'excluir_ingresso' in request.POST:
            remover_ingresso_rock(get_object_or_404(IngressoRock, id=request.POST.get('excluir_ingresso'), rock_evento=evento))
            return redirect('ingressos_rock', evento_id=evento.id)
        if form.is_valid():
            criar_ingresso_rock(evento=evento, lote=form.cleaned_data['lote'], nome=form.cleaned_data['nome'], telefone=form.cleaned_data['telefone'], quantidade_ingressos=form.cleaned_data['quantidade_ingressos'], status_pagamento=form.cleaned_data['status_pagamento'], observacao=form.cleaned_data.get('observacao'))
            return redirect('ingressos_rock', evento_id=evento.id)
    return render(request, 'core/ingressos_rock.html', {'evento': evento, 'form': form, 'ingressos': ingressos, 'can_edit_rock': can_edit_rock, 'total_recebido': sum((i.valor_total for i in ingressos), Decimal('0.00'))})


@setor_required(group_name='Rock', morador_view_attr='acesso_rock_visualizar', morador_edit_attr='acesso_rock_editar')
def exportar_ingressos_rock_pdf(request, evento_id):
    evento = get_object_or_404(RockEvento, id=evento_id)
    ingressos = IngressoRock.objects.filter(rock_evento=evento).order_by('nome')
    linhas = [f"Evento: {evento.nome} | Data: {evento.data} | Pessoas: {ingressos.count()}"] + [f"{idx}. {i.nome} | Qtd: {i.quantidade_ingressos} | Total: R$ {i.valor_total} | {i.get_status_pagamento_display()}" for idx, i in enumerate(ingressos, start=1)]
    response = HttpResponse(_gerar_pdf_simples(f'Lista de ingressos - {evento.nome}', linhas), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ingressos_rock_{evento.id}.pdf"'
    return response


@setor_required(group_name='Rock', morador_edit_attr='acesso_rock_editar')
def lotes_rock(request, evento_id):
    evento = get_object_or_404(RockEvento, id=evento_id)
    lotes = LoteIngressoRock.objects.filter(rock_evento=evento).order_by('id')
    if request.method == 'POST' and 'excluir_lote' in request.POST:
        get_object_or_404(LoteIngressoRock, id=request.POST.get('excluir_lote'), rock_evento=evento).delete()
        messages.success(request, 'Lote excluido com sucesso.')
        return redirect('lotes_rock', evento_id=evento.id)
    form = LoteIngressoRockForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        lote = form.save(commit=False); lote.rock_evento = evento; lote.save()
        return redirect('lotes_rock', evento_id=evento.id)
    return render(request, 'core/lotes_rock.html', {'evento': evento, 'form': form, 'lotes': lotes})


@login_required
def comprar_rocks(request):
    morador = get_user_morador(request.user)
    cfg = ConfiguracaoFinanceira.objects.order_by('-id').first()
    pix_recebimentos = (cfg.conta_recebimentos_pix if cfg else '') or ''
    eventos = RockEvento.objects.prefetch_related('lotes').order_by('-data')
    lotes_disponiveis = LoteIngressoRock.objects.filter(quantidade_total__gt=F('quantidade_vendida')).select_related('rock_evento').order_by('rock_evento__data', 'id')
    compra_form = CompraIngressoRockForm(request.POST or None, lotes_queryset=lotes_disponiveis)
    pedido_pagamento = None
    qr_code_data_uri = pix_payload = ''
    if request.method == 'POST' and 'iniciar_compra' in request.POST and compra_form.is_valid():
        lote = compra_form.cleaned_data['lote']
        pedido_pagamento = PedidoIngressoRock.objects.create(rock_evento=lote.rock_evento, lote=lote, usuario=request.user, nome_comprador=compra_form.cleaned_data['nome_comprador'], telefone=compra_form.cleaned_data['telefone'], quantidade=compra_form.cleaned_data['quantidade'], valor_total=lote.preco * compra_form.cleaned_data['quantidade'])
        cobranca = criar_cobranca_pix(pedido=pedido_pagamento, chave_pix=pix_recebimentos)
        pedido_pagamento.txid = cobranca.get('txid', '')
        pedido_pagamento.payload_pix = cobranca.get('payload_pix', '')
        pedido_pagamento.status_gateway = cobranca.get('status_gateway', '')
        pedido_pagamento.save(update_fields=['txid', 'payload_pix', 'status_gateway'])
        qr_code_data_uri = cobranca.get('qr_code_data_uri', '')
        pix_payload = pedido_pagamento.payload_pix
        logger.info('Pedido rock criado', extra={'pedido_id': pedido_pagamento.id})
    return render(request, 'core/comprar_rocks.html', {'morador': morador, 'eventos': eventos, 'compra_form': compra_form, 'pedido_pagamento': pedido_pagamento, 'qr_code_data_uri': qr_code_data_uri, 'pix_recebimentos': pix_recebimentos, 'pix_payload': pix_payload, 'meus_pedidos': PedidoIngressoRock.objects.filter(usuario=request.user).order_by('-criado_em')[:10]})
