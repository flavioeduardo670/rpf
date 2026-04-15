from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0058_merge_20260414_ata_conflicts"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordemservico",
            name="solicitante",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
