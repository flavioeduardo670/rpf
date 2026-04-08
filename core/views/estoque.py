import csv

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.forms import ConsumoForm, ProdutoForm
from core.models import Comodo, ConsumoEstoque, LocalArmazenamento, Produto
from core.services.estoque import ajustar_estoque_produto, garantir_setores_e_locais_base

from .common import can_edit, setor_required


@setor_required(group_name='Estoque', morador_view_attr='acesso_estoque_visualizar', morador_edit_attr='acesso_estoque_editar')
def almoxarifado(request):
    can_edit_estoque = can_edit(request, 'acesso_estoque_editar')
    garantir_setores_e_locais_base()
    produto_form = ProdutoForm(request.POST or None)
    if request.method == 'POST' and 'produto_submit' in request.POST and produto_form.is_valid():
        produto_form.save()
        return redirect('almoxarifado')
    context = {
        'produtos': Produto.objects.select_related('setor', 'local', 'local__comodo', 'local__comodo__andar').all(),
        'produto_form': produto_form,
        'can_edit_estoque': can_edit_estoque,
        'comodos': Comodo.objects.select_related('andar').order_by('andar__nome', 'nome'),
        'locais': LocalArmazenamento.objects.select_related('comodo').order_by('nome'),
    }
    return render(request, 'core/almoxarifado.html', context)


@setor_required(group_name='Estoque', morador_edit_attr='acesso_estoque_editar')
def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    if request.method == 'POST' and 'excluir_submit' in request.POST:
        produto.delete()
        return redirect('almoxarifado')
    form = ProdutoForm(request.POST or None, instance=produto)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('almoxarifado')
    return render(request, 'core/editar_produto.html', {'form': form, 'produto': produto})


@setor_required(group_name='Estoque', morador_edit_attr='acesso_estoque_editar')
def registrar_consumo(request):
    form = ConsumoForm(request.POST or None, initial={'data': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        consumo = form.save(commit=False)
        with transaction.atomic():
            produto = Produto.objects.select_for_update().get(pk=consumo.produto_id)
            if consumo.quantidade > produto.quantidade:
                form.add_error('quantidade', f'Estoque insuficiente para {produto.nome}. Disponivel: {produto.quantidade}.')
            else:
                ajustar_estoque_produto(produto.id, -consumo.quantidade)
                consumo.save()
                return redirect('consumo_historico')
    return render(request, 'core/registrar_consumo.html', {'form': form})


@setor_required(group_name='Estoque', morador_view_attr='acesso_estoque_visualizar')
def consumo_historico(request):
    return render(request, 'core/consumo_historico.html', {'consumos': ConsumoEstoque.objects.select_related('morador', 'produto').order_by('-data', '-id')})


@setor_required(group_name='Estoque', morador_view_attr='acesso_estoque_visualizar')
def exportar_consumo_csv(request):
    consumos = ConsumoEstoque.objects.select_related('morador', 'produto').order_by('-data', '-id')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="consumo_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Historico de Consumo'])
    writer.writerow(['Responsavel', 'Data', 'Item', 'Quantidade'])
    for consumo in consumos:
        writer.writerow([consumo.morador.apelido or consumo.morador.nome, consumo.data.strftime('%d/%m/%Y'), consumo.produto.nome, consumo.quantidade])
    return response


@setor_required(group_name='Estoque', morador_view_attr='acesso_estoque_visualizar')
def exportar_estoque_csv(request):
    produtos = Produto.objects.select_related('setor', 'local').order_by('nome')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="estoque_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Estoque do Almoxarifado'])
    for produto in produtos:
        writer.writerow([produto.nome, produto.descricao or '-', produto.setor.nome, produto.local.nome if produto.local else '-', produto.quantidade])
    return response
