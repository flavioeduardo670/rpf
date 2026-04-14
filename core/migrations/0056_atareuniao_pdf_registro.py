from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_reuniao_atareuniao'),
    ]

    operations = [
        migrations.AddField(
            model_name='atareuniao',
            name='arquivo_pdf',
            field=models.FileField(blank=True, null=True, upload_to='atas/'),
        ),
        migrations.AddField(
            model_name='atareuniao',
            name='participantes_texto',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='atareuniao',
            name='plano_acao_5w2h_texto',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='atareuniao',
            name='registrada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='atareuniao',
            name='topicos_texto',
            field=models.TextField(blank=True, default=''),
        ),
    ]
