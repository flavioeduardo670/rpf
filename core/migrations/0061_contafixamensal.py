from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0060_eventocalendario_campos'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContaFixaMensal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mes_referencia', models.DateField()),
                ('nome', models.CharField(max_length=100)),
                ('valor', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('ativo', models.BooleanField(default=True)),
                ('conta_fixa', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='valores_mensais', to='core.contafixa')),
            ],
            options={
                'verbose_name': 'Conta fixa mensal',
                'verbose_name_plural': 'Contas fixas mensais',
                'ordering': ['mes_referencia', 'nome', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='contafixamensal',
            index=models.Index(fields=['mes_referencia', 'ativo'], name='core_contaf_mes_ref_1ea7f2_idx'),
        ),
    ]
