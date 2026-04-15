from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import inlineformset_factory
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import (
    AtaBaseInlineFormSet,
    AtaLinha5W2HForm,
    AtaParticipanteForm,
    AtaReuniaoForm,
    AtaTopicoForm,
    ReuniaoForm,
)
from core.models import AtaLinha5W2H, AtaParticipante, AtaReuniao, AtaTopico, Reuniao

from .common import can_edit, setor_required


AtaParticipanteFormSet = inlineformset_factory(
    AtaReuniao,
    AtaParticipante,
    form=AtaParticipanteForm,
    formset=AtaBaseInlineFormSet,
    extra=1,
    can_delete=True,
)
AtaTopicoFormSet = inlineformset_factory(
    AtaReuniao,
    AtaTopico,
    form=AtaTopicoForm,
    formset=AtaBaseInlineFormSet,
    extra=1,
    can_delete=True,
)
Ata5W2HFormSet = inlineformset_factory(
    AtaReuniao,
    AtaLinha5W2H,
    form=AtaLinha5W2HForm,
    formset=AtaBaseInlineFormSet,
    extra=1,
    can_delete=True,
)


@setor_required(group_name='Reunioes', morador_view_attr='acesso_reunioes_visualizar', morador_edit_attr='acesso_reunioes_editar')
def reunioes(request):
    can_edit_reunioes = can_edit(request, 'acesso_reunioes_editar')
    form = ReuniaoForm(request.POST or None)
    if request.method == 'POST' and can_edit_reunioes and form.is_valid():
        form.save()
        messages.success(request, 'Reunião agendada com sucesso.')
        return redirect('reunioes')

    reunioes_cadastradas = Reuniao.objects.select_related('ata').all().order_by('-data', '-horario_marcado')
    return render(
        request,
        'core/reunioes.html',
        {
            'form': form,
            'reunioes': reunioes_cadastradas,
            'status_permite_ata': {'marcada', 'realizada'},
            'can_edit_reunioes': can_edit_reunioes,
        },
    )


@setor_required(group_name='Reunioes', morador_edit_attr='acesso_reunioes_editar')
def adicionar_ata_reuniao(request, reuniao_id):
    reuniao = get_object_or_404(Reuniao, pk=reuniao_id)

    if request.method != 'POST':
        return redirect('reunioes')

    if reuniao.status not in {'marcada', 'realizada'}:
        messages.error(request, 'A ata só pode ser adicionada para reuniões marcadas ou realizadas.')
        return redirect('reunioes')

    if hasattr(reuniao, 'ata'):
        messages.info(request, 'Esta reunião já possui ata cadastrada.')
        return redirect('reunioes')

    AtaReuniao.objects.create(reuniao=reuniao, criado_por=request.user)
    messages.success(request, 'Ata adicionada com sucesso.')
    return redirect('editar_ata_reuniao', reuniao_id=reuniao.id)


@setor_required(group_name='Reunioes', morador_view_attr='acesso_reunioes_visualizar', morador_edit_attr='acesso_reunioes_editar')
def editar_ata_reuniao(request, reuniao_id):
    reuniao = get_object_or_404(Reuniao, pk=reuniao_id)
    ata = getattr(reuniao, 'ata', None)
    if not ata:
        messages.error(request, 'Cadastre a ata primeiro.')
        return redirect('reunioes')

    can_edit_reunioes = can_edit(request, 'acesso_reunioes_editar')
    if request.method == 'POST' and not can_edit_reunioes:
        messages.error(request, 'Você não tem permissão de edição para registrar ata.')
        return redirect('editar_ata_reuniao', reuniao_id=reuniao.id)

    form = AtaReuniaoForm(request.POST or None, instance=ata)
    participantes_formset = AtaParticipanteFormSet(request.POST or None, instance=ata, prefix='participantes')
    topicos_formset = AtaTopicoFormSet(request.POST or None, instance=ata, prefix='topicos')
    linhas_formset = Ata5W2HFormSet(request.POST or None, instance=ata, prefix='linhas5w2h')

    if request.method == 'POST' and can_edit_reunioes:
        acao = request.POST.get('acao', 'salvar')
        valido = form.is_valid() and participantes_formset.is_valid() and topicos_formset.is_valid() and linhas_formset.is_valid()
        if valido:
            form.save()
            participantes_formset.save()
            topicos_formset.save()
            linhas_formset.save()
            if acao == 'registrar':
                try:
                    total_os = ata.registrar(registrado_por=request.user)
                except Exception as exc:
                    messages.error(request, f'Não foi possível registrar a ata: {exc}')
                else:
                    messages.success(request, f'Ata registrada com sucesso. {total_os} OS(s) gerada(s).')
                return redirect('editar_ata_reuniao', reuniao_id=reuniao.id)

            messages.success(request, 'Rascunho da ata salvo com sucesso.')
            return redirect('editar_ata_reuniao', reuniao_id=reuniao.id)

    return render(
        request,
        'core/ata_reuniao.html',
        {
            'reuniao': reuniao,
            'ata': ata,
            'form': form,
            'participantes_formset': participantes_formset,
            'topicos_formset': topicos_formset,
            'linhas_formset': linhas_formset,
            'can_edit_reunioes': can_edit_reunioes,
        },
    )


@setor_required(group_name='Reunioes', morador_view_attr='acesso_reunioes_visualizar', morador_edit_attr='acesso_reunioes_editar')
def baixar_ata_pdf(request, reuniao_id):
    reuniao = get_object_or_404(Reuniao, pk=reuniao_id)
    ata = getattr(reuniao, 'ata', None)
    if not ata or not ata.pdf_final:
        messages.error(request, 'A ata ainda não foi registrada em PDF.')
        return redirect('editar_ata_reuniao', reuniao_id=reuniao.id)
    return FileResponse(ata.pdf_final.open('rb'), content_type='application/pdf', as_attachment=True, filename=ata.pdf_final.name.split('/')[-1])
