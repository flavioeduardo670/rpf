from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0068_comprovante_enviado_e_chave_nfce'),
    ]

    operations = [
        migrations.CreateModel(
            name='ControleDistribuicaoNFe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cnpj', models.CharField(max_length=14, unique=True)),
                ('ult_nsu', models.CharField(default='000000000000000', max_length=15)),
                ('max_nsu', models.CharField(default='000000000000000', max_length=15)),
                ('ultima_consulta', models.DateTimeField(blank=True, null=True)),
                ('proxima_consulta_apos', models.DateTimeField(blank=True, null=True)),
                ('ultimo_status', models.CharField(blank=True, default='', max_length=255)),
            ],
        ),
    ]
