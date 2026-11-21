from django.db import migrations, models
from django.db.models import F


def marcar_comprovantes_antigos_como_enviados(apps, schema_editor):
    # Cobranças pagas antes deste campo existir já passaram pelo envio antigo;
    # sem isto o reenvio automático mandaria recibos repetidos.
    CobrancaAluguel = apps.get_model('core', 'CobrancaAluguel')
    CobrancaAluguel.objects.filter(status='pago', comprovante_enviado_em__isnull=True).update(
        comprovante_enviado_em=F('pago_em'),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0067_slide_inicio'),
    ]

    operations = [
        migrations.AddField(
            model_name='cobrancaaluguel',
            name='comprovante_enviado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notafiscal',
            name='chave_acesso',
            field=models.CharField(blank=True, db_index=True, default='', max_length=44),
        ),
        migrations.RunPython(marcar_comprovantes_antigos_como_enviados, migrations.RunPython.noop),
    ]
