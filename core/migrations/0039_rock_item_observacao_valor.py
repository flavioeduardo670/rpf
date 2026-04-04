from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_rock_itens'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='rockitem',
            name='nome',
        ),
        migrations.AddField(
            model_name='rockitem',
            name='observacao',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='rockitem',
            name='valor_unitario',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
