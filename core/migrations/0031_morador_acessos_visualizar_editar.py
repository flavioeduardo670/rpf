from django.db import migrations, models


def copiar_acessos(apps, schema_editor):
    Morador = apps.get_model('core', 'Morador')
    for morador in Morador.objects.all():
        morador.acesso_financeiro_visualizar = morador.acesso_financeiro
        morador.acesso_financeiro_editar = morador.acesso_financeiro
        morador.acesso_compras_visualizar = morador.acesso_compras
        morador.acesso_compras_editar = morador.acesso_compras
        morador.acesso_estoque_visualizar = morador.acesso_estoque
        morador.acesso_estoque_editar = morador.acesso_estoque
        morador.acesso_manutencao_visualizar = morador.acesso_manutencao
        morador.acesso_manutencao_editar = morador.acesso_manutencao
        morador.acesso_rock_visualizar = False
        morador.acesso_rock_editar = False
        morador.save(
            update_fields=[
                'acesso_financeiro_visualizar',
                'acesso_financeiro_editar',
                'acesso_compras_visualizar',
                'acesso_compras_editar',
                'acesso_estoque_visualizar',
                'acesso_estoque_editar',
                'acesso_manutencao_visualizar',
                'acesso_manutencao_editar',
                'acesso_rock_visualizar',
                'acesso_rock_editar',
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_pendencia_mensal'),
    ]

    operations = [
        migrations.AddField(
            model_name='morador',
            name='acesso_financeiro_visualizar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_financeiro_editar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_compras_visualizar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_compras_editar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_estoque_visualizar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_estoque_editar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_manutencao_visualizar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_manutencao_editar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_rock_visualizar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_rock_editar',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(copiar_acessos, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='morador',
            name='acesso_financeiro',
        ),
        migrations.RemoveField(
            model_name='morador',
            name='acesso_compras',
        ),
        migrations.RemoveField(
            model_name='morador',
            name='acesso_estoque',
        ),
        migrations.RemoveField(
            model_name='morador',
            name='acesso_manutencao',
        ),
    ]
