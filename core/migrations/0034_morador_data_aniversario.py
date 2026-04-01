from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_morador_curso_funcoes'),
    ]

    operations = [
        migrations.AddField(
            model_name='morador',
            name='data_aniversario',
            field=models.DateField(blank=True, null=True),
        ),
    ]
