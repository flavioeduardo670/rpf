from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_ingressorock'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LoteIngressoRock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('quantidade_total', models.PositiveIntegerField(default=0)),
                ('quantidade_vendida', models.PositiveIntegerField(default=0)),
                ('preco', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('rock_evento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lotes', to='core.rockevento')),
            ],
        ),
        migrations.CreateModel(
            name='PedidoIngressoRock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_comprador', models.CharField(max_length=150)),
                ('telefone', models.CharField(blank=True, max_length=30, null=True)),
                ('quantidade', models.PositiveIntegerField(default=1)),
                ('valor_total', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('status', models.CharField(choices=[('aguardando_pagamento', 'Aguardando pagamento'), ('pago', 'Pago')], default='aguardando_pagamento', max_length=30)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('pago_em', models.DateTimeField(blank=True, null=True)),
                ('lote', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pedidos', to='core.loteingressorock')),
                ('rock_evento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pedidos_ingresso', to='core.rockevento')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
