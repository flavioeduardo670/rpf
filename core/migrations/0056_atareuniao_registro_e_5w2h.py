from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0055_reuniao_atareuniao"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="atareuniao",
            name="gerou_os",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="atareuniao",
            name="pdf_final",
            field=models.FileField(blank=True, null=True, upload_to="atas/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="atareuniao",
            name="registrada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="atareuniao",
            name="registrada_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="atas_registradas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="atareuniao",
            name="status",
            field=models.CharField(
                choices=[("rascunho", "Rascunho"), ("registrada", "Registrada")],
                default="rascunho",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="AtaParticipante",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nome", models.CharField(max_length=150)),
                ("presente", models.BooleanField(default=True)),
                (
                    "ata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participantes",
                        to="core.atareuniao",
                    ),
                ),
            ],
            options={"ordering": ["nome"]},
        ),
        migrations.CreateModel(
            name="AtaTopico",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ordem", models.PositiveIntegerField(default=1)),
                ("texto", models.TextField()),
                (
                    "ata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="topicos",
                        to="core.atareuniao",
                    ),
                ),
            ],
            options={"ordering": ["ordem", "id"]},
        ),
        migrations.CreateModel(
            name="AtaLinha5W2H",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("o_que", models.CharField(blank=True, default="", max_length=255)),
                ("por_que", models.TextField(blank=True, default="")),
                ("onde", models.CharField(blank=True, default="", max_length=255)),
                ("quem", models.CharField(blank=True, default="", max_length=150)),
                ("quando", models.DateField(blank=True, null=True)),
                ("como", models.TextField(blank=True, default="")),
                ("quanto", models.CharField(blank=True, default="", max_length=120)),
                (
                    "ata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="linhas_5w2h",
                        to="core.atareuniao",
                    ),
                ),
                (
                    "ordem_servico",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="origem_5w2h",
                        to="core.ordemservico",
                    ),
                ),
            ],
        ),
    ]
