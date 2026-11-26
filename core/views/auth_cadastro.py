import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from core.forms import EventoCalendarioForm
from core.models import EventoCalendario, OrdemServico, Organizacao, Reuniao, RockEvento

from .common import can_edit, get_user_morador, setor_required


# Atalhos da página inicial: (variante do boneco, rota, título, descrição, módulo de permissão)
# Textos entre chaves vêm do vocabulário do cliente (core/terminologia.py).
ATALHOS = [
    ('financeiro', 'financeiro', 'Financeiro', '{Cobranca}, rateio e prestação de contas.', 'financeiro'),
    ('compras', 'compras', 'Compras', 'Notas fiscais e parcelas {do_local}.', 'compras'),
    ('almoxarifado', 'almoxarifado', 'Almoxarifado', 'Estoque e consumo de produtos.', 'estoque'),
    ('manutencao', 'manutencao', 'Ordens de serviço', 'O que precisa de conserto.', 'manutencao'),
    ('rock', 'rock', '{Eventos}', 'Datas, lotes e ingressos.', 'rock'),
    ('reunioes', 'reunioes', 'Reuniões', 'Pautas e atas registradas.', 'reunioes'),
    ('calendario', 'calendario', 'Calendário', 'Tudo que vai acontecer no mês.', 'reunioes'),
    ('moradores', 'moradores', '{Membros}', '{Unidades}, cursos e funções.', None),
    ('perfil', 'perfil', 'Meu perfil', 'Seus dados e comprovantes.', None),
]


# Blocos que ganham destaque na grade de atalhos (os demais ficam com contorno).
ESTILO_ATALHO = {'financeiro': 'destaque', 'rock': 'escuro', 'calendario': 'largo'}


def _saudacao(agora):
    if 5 <= agora.hour < 12:
        return 'Bom dia'
    if 12 <= agora.hour < 18:
        return 'Boa tarde'
    return 'Boa noite'


def _resumo_areas(termos, ativos):
    """'contas, compras, rocks e reuniões', só com os módulos ligados."""
    partes = [
        texto for modulo, texto in (
            ('financeiro', 'contas'), ('compras', 'compras'), ('rock', termos['eventos']), ('reunioes', 'reuniões'),
        ) if modulo in ativos
    ]
    if len(partes) > 1:
        return f"{', '.join(partes[:-1])} e {partes[-1]}"
    return partes[0] if partes else ''


def _avisos_casa(termos, ativos):
    """Próximo evento (rock) e próxima reunião, se esses módulos estiverem ligados."""
    hoje = timezone.localdate()
    avisos = []
    if 'rock' in ativos:
        rock = RockEvento.objects.filter(data__gte=hoje).order_by('data').first()
        avisos.append(
            f'Próximo {termos["evento"]}: {rock.nome}, {rock.data:%d/%m}' if rock
            else f'Nenhum {termos["evento"]} marcado ainda'
        )
    if 'reunioes' in ativos:
        reuniao = Reuniao.objects.filter(data__gte=hoje, status='marcada').order_by('data', 'horario_marcado').first()
        avisos.append(
            f'Próxima reunião: {reuniao.data:%d/%m}, às {reuniao.horario_marcado:%H:%M}'
            if reuniao else 'Nenhuma reunião marcada'
        )
    return avisos


@login_required
def home(request):
    from django.urls import reverse

    from core.context_processors import imagens_boneco, pode_ver_modulo

    morador = get_user_morador(request.user)
    organizacao = Organizacao.atual()
    termos = organizacao.vocabulario
    ativos = organizacao.modulos_ativos

    atalhos = []
    for variante, rota, titulo, descricao, modulo in ATALHOS:
        if variante != 'perfil' and variante not in ativos:
            continue
        if variante == 'rock' and morador is None and not request.user.is_superuser:
            # Quem não é membro da organização só compra ingressos.
            atalhos.append({'variante': 'rock', 'url': reverse('comprar_rocks'), 'titulo': 'Ingressos',
                            'descricao': 'Compre ingressos para {os_eventos}.'.format_map(termos),
                            'estilo': ESTILO_ATALHO['rock']})
            continue
        if pode_ver_modulo(request.user, modulo):
            atalhos.append({'variante': variante, 'url': reverse(rota), 'titulo': titulo.format_map(termos),
                            'descricao': descricao.format_map(termos), 'estilo': ESTILO_ATALHO.get(variante, '')})

    # Botões da saudação: financeiro e calendário, quando a pessoa pode abrir essas seções.
    rotulos_acao = {'financeiro': 'Abrir financeiro', 'calendario': 'Ver calendário'}
    acoes = [{'url': a['url'], 'rotulo': rotulos_acao[a['variante']]} for a in atalhos if a['variante'] in rotulos_acao]

    return render(request, 'core/home.html', {
        'usuario_sem_vinculo': morador is None,
        'atalhos': atalhos,
        'acoes': acoes,
        'saudacao': _saudacao(timezone.localtime()),
        'avisos': _avisos_casa(termos, ativos),
        'resumo_areas': _resumo_areas(termos, ativos),
        'loop_inicio': imagens_boneco('inicio')['loop'],
    })


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
    # O calendário só mostra itens dos módulos que o cliente ligou.
    ativos = Organizacao.atual().modulos_ativos
    rocks = RockEvento.objects.filter(data__range=(start, end)) if 'rock' in ativos else []
    ordens = OrdemServico.objects.filter(data_inicio__date__range=(start, end)) if 'manutencao' in ativos else []
    reunioes_mes = Reuniao.objects.filter(data__range=(start, end)) if 'reunioes' in ativos else []

    for rock in rocks:
        eventos_por_dia[rock.data].append({'origem': 'rock', 'texto': rock.nome})
    for os in ordens:
        eventos_por_dia[os.data_inicio.date()].append({'origem': 'os', 'texto': f"OS {os.numero}"})
    for reuniao in reunioes_mes:
        titulo = f"Reunião {reuniao.get_tipo_display()}"
        if reuniao.tipo == 'setorial' and reuniao.setor:
            titulo = f"{titulo} - {reuniao.get_setor_display()}"
        eventos_por_dia[reuniao.data].append({'origem': 'reuniao', 'texto': titulo})
    eventos_manuais_mes = list(EventoCalendario.objects.filter(data__range=(start, end), recorrente=False))
    eventos_recorrentes = list(EventoCalendario.objects.filter(recorrente=True, data__lte=end))

    for manual in eventos_manuais_mes:
        texto = manual.titulo if manual.dia_todo or not manual.horario else f"{manual.horario.strftime('%H:%M')} - {manual.titulo}"
        eventos_por_dia[manual.data].append({'origem': 'manual', 'texto': texto, 'cor': manual.cor})

    for manual in eventos_recorrentes:
        ultimo_dia_mes = calendar.monthrange(current.year, current.month)[1]
        dia_referencia = min(manual.data.day, ultimo_dia_mes)
        data_ocorrencia = current.replace(day=dia_referencia)
        if data_ocorrencia < manual.data:
            continue
        texto_base = f"{manual.titulo} (recorrente)"
        texto = texto_base if manual.dia_todo or not manual.horario else f"{manual.horario.strftime('%H:%M')} - {texto_base}"
        eventos_por_dia[data_ocorrencia].append({'origem': 'manual', 'texto': texto, 'cor': manual.cor})

    weeks = [
        [{'date': day, 'events': eventos_por_dia.get(day, [])} for day in week]
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(current.year, current.month)
    ]
    eventos_manuais = EventoCalendario.objects.filter(
        data__range=(start, end)
    ).order_by('data', 'titulo')

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
