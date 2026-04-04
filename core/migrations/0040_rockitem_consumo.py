from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_rock_item_observacao_valor'),
    ]

    operations = [
        migrations.AddField(
            model_name='rockitem',
            name='consumo',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.consumoestoque'),
        ),
    ]
