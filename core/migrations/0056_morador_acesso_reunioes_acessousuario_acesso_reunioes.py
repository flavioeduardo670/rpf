from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_reuniao_atareuniao'),
    ]

    operations = [
        migrations.AddField(
            model_name='acessousuario',
            name='acesso_reunioes_editar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='acessousuario',
            name='acesso_reunioes_visualizar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_reunioes_editar',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='morador',
            name='acesso_reunioes_visualizar',
            field=models.BooleanField(default=False),
        ),
    ]
