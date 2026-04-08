import csv

from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from core.forms import MoradorEdicaoForm, PerfilFotoForm
from core.models import Morador, OrdemServico

from .common import get_user_morador

MoradorEdicaoFormSet = modelformset_factory(Morador, form=MoradorEdicaoForm, extra=0)


@login_required
def perfil(request):
    morador = get_user_morador(request.user)
    ordens = []
    novas_ordens = []
    if request.method == 'POST' and morador:
        foto_form = PerfilFotoForm(request.POST, request.FILES, instance=morador)
        if foto_form.is_valid():
            foto_form.save()
            return redirect('perfil')
    else:
        foto_form = PerfilFotoForm(instance=morador)

    if morador:
        ordens = OrdemServico.objects.filter(executado_por=morador.nome).order_by('-data_inicio')[:20]
        novas_ordens = OrdemServico.objects.filter(status='aberta').exclude(executado_por=morador.nome).order_by('-data_inicio')[:10]

    return render(request, 'core/perfil.html', {'morador': morador, 'foto_form': foto_form, 'ordens': ordens, 'novas_ordens': novas_ordens})


@login_required
def moradores(request):
    moradores_qs = Morador.objects.order_by('ordem_hierarquia', 'nome')
    if request.method == 'POST':
        formset = MoradorEdicaoFormSet(request.POST, queryset=moradores_qs)
        if formset.is_valid():
            formset.save()
            return redirect('moradores')
    else:
        formset = MoradorEdicaoFormSet(queryset=moradores_qs)
    return render(request, 'core/moradores.html', {'formset': formset})


@login_required
def exportar_moradores_csv(request):
    moradores_qs = Morador.objects.order_by('ordem_hierarquia', 'nome')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="moradores_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Moradores'])
    writer.writerow(['Nome', 'Apelido', 'Email', 'Quarto', 'Curso', 'Funções', 'Ativo'])
    for morador in moradores_qs:
        writer.writerow([morador.nome, morador.apelido or '-', morador.email or '-', morador.quarto or '-', morador.curso or '-', morador.funcoes or '-', 'Sim' if morador.ativo else 'Nao'])
    return response
