from django.db import migrations, models


def preencher_motivo(apps, schema_editor):
    PendenciaMensalItem = apps.get_model('core', 'PendenciaMensalItem')
    PendenciaMensalItem.objects.filter(motivo='').update(motivo=models.F('descricao'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_pendencia_item_e_rateio_exclusao'),
    ]

    operations = [
        migrations.AddField(
            model_name='pendenciamensalitem',
            name='tipo',
            field=models.CharField(choices=[('extra', 'Extra'), ('desconto', 'Desconto')], default='extra', max_length=20),
        ),
        migrations.AddField(
            model_name='pendenciamensalitem',
            name='motivo',
            field=models.CharField(default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='pendenciamensalitem',
            name='descricao',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.RunPython(preencher_motivo, migrations.RunPython.noop),
    ]
