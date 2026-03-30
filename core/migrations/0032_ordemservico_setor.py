from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_morador_acessos_visualizar_editar'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordemservico',
            name='setor',
            field=models.CharField(
                choices=[
                    ('manutencao', 'Manutencao'),
                    ('infraestrutura', 'Infraestrutura'),
                    ('hotelaria', 'Hotelaria'),
                    ('rock', 'Rock'),
                    ('outros', 'Outros'),
                ],
                default='manutencao',
                max_length=20,
            ),
        ),
    ]
