from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ReuniaoForm
from core.models import AtaReuniao, Reuniao


@login_required
def reunioes(request):
    form = ReuniaoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
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
        },
    )


@login_required
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
    return redirect('reunioes')
