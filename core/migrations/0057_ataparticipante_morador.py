from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0056_atareuniao_registro_e_5w2h"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE core_ataparticipante "
                        "ADD COLUMN IF NOT EXISTS nome varchar(150) NOT NULL DEFAULT '';"
                    ),
                    reverse_sql=(
                        "ALTER TABLE core_ataparticipante "
                        "DROP COLUMN IF EXISTS nome;"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="ataparticipante",
                    name="nome",
                    field=models.CharField(blank=True, default="", max_length=150),
                ),
            ],
        ),
    ]
