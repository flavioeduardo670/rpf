from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_ordemservico_setor'),
    ]

    operations = [
        migrations.AddField(
            model_name='morador',
            name='curso',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='morador',
            name='funcoes',
            field=models.TextField(blank=True, null=True),
        ),
    ]

