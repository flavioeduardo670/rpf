from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_eventocalendario'),
    ]

    operations = [
        migrations.AddField(
            model_name='morador',
            name='ultima_visualizacao_os',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
