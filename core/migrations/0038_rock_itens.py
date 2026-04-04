from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_choice_lists'),
    ]

    operations = [
        migrations.AddField(
            model_name='notafiscal',
            name='rock_evento',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.rockevento'),
        ),
        migrations.AddField(
            model_name='rockevento',
            name='horario_inicio',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='rockevento',
            name='horario_fim',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='RockItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(blank=True, max_length=200)),
                ('quantidade', models.IntegerField(default=1)),
                ('produto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.produto')),
                ('rock_evento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='core.rockevento')),
            ],
        ),
    ]
