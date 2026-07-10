# Generated manually for the finance house bills module.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0063_cobrancaaluguel'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContaCasa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('data_vencimento', models.DateField()),
                ('mes_cobranca_aluguel', models.DateField()),
                ('valor', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('forma_pagamento', models.CharField(blank=True, default='', max_length=100)),
                ('repetir_meses_futuros', models.BooleanField(default=False)),
                ('ativo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Conta da casa',
                'verbose_name_plural': 'Contas da casa',
                'ordering': ['mes_cobranca_aluguel', 'data_vencimento', 'nome', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='contacasa',
            index=models.Index(fields=['mes_cobranca_aluguel', 'ativo'], name='core_contac_mes_cob_5f385d_idx'),
        ),
        migrations.AddIndex(
            model_name='contacasa',
            index=models.Index(fields=['data_vencimento'], name='core_contac_data_ve_a752c5_idx'),
        ),
    ]
