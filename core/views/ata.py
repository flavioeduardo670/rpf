from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.forms import AtaReuniaoForm
from core.models import AtaReuniao, Reuniao
from core.services.ata_pdf import gerar_pdf_ata


@login_required
def editar_ata_reuniao(request, reuniao_id):
    reuniao = get_object_or_404(Reuniao, pk=reuniao_id)
    ata, _ = AtaReuniao.objects.get_or_create(
        reuniao=reuniao,
        defaults={'criado_por': request.user},
    )

    if ata.registrada_em:
        return render(
            request,
            'core/editar_ata_reuniao.html',
            {'ata': ata, 'reuniao': reuniao, 'somente_leitura': True, 'form': None},
        )

    form = AtaReuniaoForm(request.POST or None, instance=ata)

    if request.method == 'POST':
        if not form.is_valid():
            messages.error(request, 'Nao foi possivel salvar a ata. Verifique os campos obrigatorios.')
        elif 'registrar_pdf' in request.POST:
            ata = form.save(commit=False)
            if not ata.criado_por_id:
                ata.criado_por = request.user
            pdf_bytes = gerar_pdf_ata(ata)
            nome_arquivo = f"ata-{ata.identificador_formatado.lower().replace(' ', '-')}.pdf"
            ata.arquivo_pdf.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
            ata.registrada_em = timezone.now()
            ata.save()
            messages.success(request, 'Ata registrada com sucesso. O PDF final foi salvo no historico.')
            return redirect('editar_ata_reuniao', reuniao_id=reuniao.id)
        else:
            ata = form.save(commit=False)
            if not ata.criado_por_id:
                ata.criado_por = request.user
            ata.save()
            messages.success(request, 'Rascunho da ata salvo com sucesso.')
            return redirect('editar_ata_reuniao', reuniao_id=reuniao.id)

    return render(
        request,
        'core/editar_ata_reuniao.html',
        {'ata': ata, 'reuniao': reuniao, 'form': form, 'somente_leitura': False},
    )


@login_required
def download_ata_pdf(request, ata_id):
    ata = get_object_or_404(AtaReuniao, pk=ata_id)
    if not ata.arquivo_pdf:
        raise Http404('Ata ainda nao possui PDF registrado.')
    return redirect(ata.arquivo_pdf.url)
