from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0056_atareuniao_registro_e_5w2h"),
    ]

    operations = [
        migrations.AddField(
            model_name="ataparticipante",
            name="morador",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="core.morador",
            ),
        ),
        migrations.AlterField(
            model_name="ataparticipante",
            name="nome",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
