from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0062_registrofinanceiromensal'),
    ]

    operations = [
        migrations.CreateModel(
            name='CobrancaAluguel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mes_referencia', models.DateField()),
                ('valor', models.DecimalField(decimal_places=2, max_digits=10)),
                ('txid', models.CharField(blank=True, db_index=True, default='', max_length=40)),
                ('payload_pix', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('aguardando_pagamento', 'Aguardando pagamento'), ('pago', 'Pago'), ('cancelado', 'Cancelado')], default='aguardando_pagamento', max_length=30)),
                ('status_gateway', models.CharField(blank=True, default='', max_length=40)),
                ('provider_payload', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('webhook_recebido_em', models.DateTimeField(blank=True, null=True)),
                ('pago_em', models.DateTimeField(blank=True, null=True)),
                ('morador', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cobrancas_aluguel', to='core.morador')),
            ],
            options={
                'ordering': ['-mes_referencia', 'morador__nome'],
                'unique_together': {('morador', 'mes_referencia')},
            },
        ),
    ]
