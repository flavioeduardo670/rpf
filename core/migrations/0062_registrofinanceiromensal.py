from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0061_contafixamensal'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistroFinanceiroMensal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mes_referencia', models.DateField(unique=True)),
                ('valor_aluguel', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('valor_fixas_total', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_caixinha_mes', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_parcelas_mes_rateio', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('desconto_total_mes', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('pendencia_total_mes', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_rateio', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_a_arrecadar', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_moradores', models.PositiveIntegerField(default=0)),
                ('salvo_em', models.DateTimeField(auto_now=True)),
                ('salvo_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Registro financeiro mensal',
                'verbose_name_plural': 'Registros financeiros mensais',
                'ordering': ['-mes_referencia'],
            },
        ),
        migrations.CreateModel(
            name='RegistroFinanceiroMorador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('morador_nome', models.CharField(max_length=100)),
                ('morador_apelido', models.CharField(blank=True, default='', max_length=50)),
                ('ordem_hierarquia', models.PositiveIntegerField(default=0)),
                ('peso_quarto', models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ('aluguel', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('fixas', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('fixas_detalhe', models.JSONField(blank=True, default=list)),
                ('caixinha', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('parcelas', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('desconto', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('extra', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('valor', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('morador', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.morador')),
                ('registro', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='moradores', to='core.registrofinanceiromensal')),
            ],
            options={
                'verbose_name': 'Registro financeiro por morador',
                'verbose_name_plural': 'Registros financeiros por morador',
                'ordering': ['ordem_hierarquia', 'morador_nome'],
            },
        ),
    ]
