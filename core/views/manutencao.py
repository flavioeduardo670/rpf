from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import OrdemServicoForm, TransferirSituacaoOSForm
from core.models import NotaFiscal, OrdemServico
from core.services.estoque import remover_consumo_e_devolver_estoque

from .common import can_edit, get_user_morador, setor_required

@setor_required(group_name='Manutencao', morador_view_attr='acesso_manutencao_visualizar', morador_edit_attr='acesso_manutencao_editar')
def manutencao(request):
    can_edit_manutencao = can_edit(request, 'acesso_manutencao_editar')
    os_form = OrdemServicoForm(request.POST or None)
    if request.method == 'POST' and os_form.is_valid():
        os_nova = os_form.save(commit=False)
        morador = get_user_morador(request)
        if morador:
            os_nova.solicitante = morador.apelido or morador.nome
        elif request.user.is_authenticated:
            os_nova.solicitante = request.user.get_username()
        os_nova.save()
        return redirect('manutencao')

    ordens = OrdemServico.objects.all().order_by('numero')
    ordens_ativas = ordens.filter(status__iexact='aberta', data_fim__isnull=True)
    ordens_finalizadas = ordens.exclude(status__iexact='aberta', data_fim__isnull=True)
    return render(request, 'core/manutencao.html', {
        'os_form': os_form,
        'ordens_ativas': ordens_ativas,
        'ordens_finalizadas': ordens_finalizadas,
        'can_edit_manutencao': can_edit_manutencao,
    })


@setor_required(group_name='Manutencao', morador_view_attr='acesso_manutencao_visualizar')
def lista_os(request):
    ordens = OrdemServico.objects.all().order_by('numero')
    return render(request, 'core/lista_os.html', {
        'ordens_ativas': ordens.filter(status__iexact='aberta', data_fim__isnull=True),
        'ordens_finalizadas': ordens.exclude(status__iexact='aberta', data_fim__isnull=True),
    })


@setor_required(group_name='Manutencao', morador_edit_attr='acesso_manutencao_editar')
def editar_os(request, numero):
    os_obj = get_object_or_404(OrdemServico, numero=numero)
    if request.method == 'POST' and 'excluir_os' in request.POST:
        with transaction.atomic():
            for material in os_obj.materiais.select_related('consumo'):
                remover_consumo_e_devolver_estoque(getattr(material, 'consumo', None))
            if os_obj.despesa_gerada:
                NotaFiscal.objects.filter(setor='manutencao', descricao=f"Manutenção OS #{os_obj.numero}").delete()
        os_obj.delete()
        return redirect('manutencao')

    os_form = OrdemServicoForm(request.POST or None, instance=os_obj)
    if request.method == 'POST' and os_form.is_valid():
        with transaction.atomic():
            os_salva = os_form.save()
            if os_salva.status == 'finalizada' and not os_salva.despesa_gerada:
                os_salva.gerar_despesa()
        return redirect('manutencao')

    return render(request, 'core/editar_os.html', {'os_form': os_form, 'os': os_obj})


@setor_required(group_name='Manutencao', morador_edit_attr='acesso_manutencao_editar')
def transferir_situacao_os(request, numero):
    os_obj = get_object_or_404(OrdemServico, numero=numero)
    form = TransferirSituacaoOSForm(request.POST or None, instance=os_obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            os_salva = form.save()
            if os_salva.status == 'finalizada' and not os_salva.despesa_gerada:
                os_salva.gerar_despesa()
        return redirect('manutencao')
    return render(request, 'core/transferir_situacao_os.html', {'os': os_obj, 'form': form})
