from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0056_atareuniao_registro_e_5w2h"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ataparticipante",
            name="nome",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
