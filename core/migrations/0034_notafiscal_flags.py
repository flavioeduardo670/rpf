from django.db import migrations, models


def set_flags(apps, schema_editor):
    NotaFiscal = apps.get_model('core', 'NotaFiscal')
    for nota in NotaFiscal.objects.all():
        adicionar_estoque = bool(nota.quantidade and nota.quantidade > 0)
        cobrar_no_aluguel = nota.tipo_item in ('Bem de Consumo', 'Bem Material') and nota.categoria_compra != 'rock'
        NotaFiscal.objects.filter(pk=nota.pk).update(
            adicionar_estoque=adicionar_estoque,
            cobrar_no_aluguel=cobrar_no_aluguel,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_morador_curso_funcoes'),
    ]

    operations = [
        migrations.AddField(
            model_name='notafiscal',
            name='adicionar_estoque',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='notafiscal',
            name='cobrar_no_aluguel',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(set_flags, migrations.RunPython.noop),
    ]
