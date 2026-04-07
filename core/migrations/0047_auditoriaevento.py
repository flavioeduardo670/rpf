from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_loteingressorock_pedidoingressorock'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditoriaEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('configuracao_financeira_pix', 'Configuracao financeira PIX'), ('vinculo_user_morador', 'Vinculo User/Morador'), ('pedido_ingresso_status', 'Status de pedido de ingresso')], max_length=60)),
                ('descricao', models.CharField(max_length=255)),
                ('entidade', models.CharField(blank=True, default='', max_length=80)),
                ('entidade_id', models.PositiveIntegerField(blank=True, null=True)),
                ('dados', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-criado_em', '-id'],
            },
        ),
    ]
