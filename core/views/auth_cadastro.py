import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from core.forms import EventoCalendarioForm
from core.models import EventoCalendario, OrdemServico, Reuniao, RockEvento

from .common import can_edit, get_user_morador, setor_required


@login_required
def home(request):
    morador = get_user_morador(request.user)
    return render(request, 'core/home.html', {'usuario_sem_vinculo': morador is None})


@setor_required(
    group_name='Reunioes',
    morador_view_attr='acesso_reunioes_visualizar',
    morador_edit_attr='acesso_reunioes_editar',
)
def calendario(request):
    today = timezone.localdate()
    mes_param = request.GET.get('mes')
    try:
        current = date(*[int(x) for x in mes_param.split('-')], 1) if mes_param else today.replace(day=1)
    except ValueError:
        current = today.replace(day=1)

    can_edit_reunioes = can_edit(request, 'acesso_reunioes_editar')

    editar_evento_id = request.GET.get('editar_evento')
    evento_em_edicao = None
    if editar_evento_id:
        evento_em_edicao = EventoCalendario.objects.filter(pk=editar_evento_id).first()

    if request.method == 'POST':
        acao = request.POST.get('acao', 'criar_manual')
        evento_id = request.POST.get('evento_id')
        if acao == 'excluir_manual':
            EventoCalendario.objects.filter(pk=evento_id).delete()
            return redirect(f"{redirect('calendario').url}?mes={current.strftime('%Y-%m')}")

        if acao == 'editar_manual':
            evento_em_edicao = EventoCalendario.objects.filter(pk=evento_id).first()
            form = EventoCalendarioForm(request.POST, instance=evento_em_edicao)
        else:
            form = EventoCalendarioForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect(f"{redirect('calendario').url}?mes={current.strftime('%Y-%m')}")
    else:
        if evento_em_edicao:
            form = EventoCalendarioForm(instance=evento_em_edicao)
        else:
            form = EventoCalendarioForm(initial={'data': today})

    start = current
    end = (current + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    eventos_por_dia = defaultdict(list)

    for rock in RockEvento.objects.filter(data__range=(start, end)):
        eventos_por_dia[rock.data].append({'origem': 'rock', 'texto': rock.nome})
    for os in OrdemServico.objects.filter(data_inicio__date__range=(start, end)):
        eventos_por_dia[os.data_inicio.date()].append({'origem': 'os', 'texto': f"OS {os.numero}"})
    for reuniao in Reuniao.objects.filter(data__range=(start, end)):
        titulo = f"Reunião {reuniao.get_tipo_display()}"
        if reuniao.tipo == 'setorial' and reuniao.setor:
            titulo = f"{titulo} - {reuniao.get_setor_display()}"
        eventos_por_dia[reuniao.data].append({'origem': 'reuniao', 'texto': titulo})
    for manual in EventoCalendario.objects.filter(data__range=(start, end)):
        eventos_por_dia[manual.data].append({'origem': 'manual', 'texto': manual.titulo})

    weeks = [
        [{'date': day, 'events': eventos_por_dia.get(day, [])} for day in week]
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(current.year, current.month)
    ]
    eventos_manuais = EventoCalendario.objects.filter(data__range=(start, end)).order_by('data', 'titulo')

    return render(
        request,
        'core/calendario.html',
        {
            'form': form,
            'current': current,
            'today': today,
            'weeks': weeks,
            'dias_semana': ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'],
            'eventos_por_dia': eventos_por_dia,
            'mes_anterior': (current - timedelta(days=1)).replace(day=1),
            'mes_proximo': (current + timedelta(days=32)).replace(day=1),
            'can_edit_reunioes': can_edit_reunioes,
            'eventos_manuais': eventos_manuais,
            'evento_em_edicao': evento_em_edicao,
        },
    )


def cadastro(request):
    raise Http404('Cadastro publico desativado.')
