from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0050_alter_morador_foto_perfil'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendenciaMensalItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mes_referencia', models.DateField()),
                ('descricao', models.CharField(max_length=200)),
                ('valor', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='ParcelaRateioExclusao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('morador', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.morador')),
                ('parcela', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rateio_exclusoes', to='core.notaparcela')),
            ],
            options={
                'unique_together': {('parcela', 'morador')},
            },
        ),
    ]
