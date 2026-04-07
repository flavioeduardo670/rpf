from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_morador_ultima_visualizacao_os'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AcessoUsuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acesso_financeiro_visualizar', models.BooleanField(default=False)),
                ('acesso_financeiro_editar', models.BooleanField(default=False)),
                ('acesso_compras_visualizar', models.BooleanField(default=False)),
                ('acesso_compras_editar', models.BooleanField(default=False)),
                ('acesso_estoque_visualizar', models.BooleanField(default=False)),
                ('acesso_estoque_editar', models.BooleanField(default=False)),
                ('acesso_manutencao_visualizar', models.BooleanField(default=False)),
                ('acesso_manutencao_editar', models.BooleanField(default=False)),
                ('acesso_rock_visualizar', models.BooleanField(default=False)),
                ('acesso_rock_editar', models.BooleanField(default=False)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='acesso_usuario', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
