import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from core.forms import EventoCalendarioForm
from core.models import EventoCalendario, OrdemServico, RockEvento

from .common import get_user_morador


@login_required
def home(request):
    morador = get_user_morador(request.user)
    return render(request, 'core/home.html', {'usuario_sem_vinculo': morador is None})


@login_required
def calendario(request):
    today = timezone.localdate()
    mes_param = request.GET.get('mes')
    try:
        current = date(*[int(x) for x in mes_param.split('-')], 1) if mes_param else today.replace(day=1)
    except ValueError:
        current = today.replace(day=1)

    if request.method == 'POST':
        form = EventoCalendarioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(f"{redirect('calendario').url}?mes={current.strftime('%Y-%m')}")
    else:
        form = EventoCalendarioForm(initial={'data': today})

    start = current
    end = (current + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    eventos_por_dia = defaultdict(list)

    for rock in RockEvento.objects.filter(data__range=(start, end)):
        eventos_por_dia[rock.data].append(rock.nome)
    for os in OrdemServico.objects.filter(data_inicio__date__range=(start, end)):
        eventos_por_dia[os.data_inicio.date()].append(f"OS {os.numero}")
    for manual in EventoCalendario.objects.filter(data__range=(start, end)):
        eventos_por_dia[manual.data].append(manual.titulo)

    weeks = [
        [{'date': day, 'events': eventos_por_dia.get(day, [])} for day in week]
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(current.year, current.month)
    ]
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
        },
    )


def cadastro(request):
    raise Http404('Cadastro publico desativado.')
