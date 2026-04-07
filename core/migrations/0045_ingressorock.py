from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_acessousuario'),
    ]

    operations = [
        migrations.CreateModel(
            name='IngressoRock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=150)),
                ('telefone', models.CharField(blank=True, max_length=30, null=True)),
                ('quantidade_ingressos', models.PositiveIntegerField(default=1)),
                ('valor_unitario', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('status_pagamento', models.CharField(choices=[('pendente', 'Pendente'), ('pago', 'Pago')], default='pendente', max_length=20)),
                ('observacao', models.CharField(blank=True, max_length=200, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('rock_evento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ingressos', to='core.rockevento')),
            ],
        ),
    ]
