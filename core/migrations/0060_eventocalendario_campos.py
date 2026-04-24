from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0059_ordemservico_solicitante'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventocalendario',
            name='cor',
            field=models.CharField(default='#ececec', max_length=7),
        ),
        migrations.AddField(
            model_name='eventocalendario',
            name='dia_todo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='eventocalendario',
            name='horario',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='eventocalendario',
            name='recorrente',
            field=models.BooleanField(default=False),
        ),
    ]
