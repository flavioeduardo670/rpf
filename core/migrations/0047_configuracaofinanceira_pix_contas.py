from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_loteingressorock_pedidoingressorock'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracaofinanceira',
            name='conta_pagamentos_pix',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='configuracaofinanceira',
            name='conta_principal_pix',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='configuracaofinanceira',
            name='conta_recebimentos_pix',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
