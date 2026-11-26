from django.db import migrations


def preencher_organizacao(apps, schema_editor):
    """Todo dado que já existe é da primeira organização (a Portão)."""
    Organizacao = apps.get_model('core', 'Organizacao')
    org = Organizacao.objects.order_by('id').first()
    if org is None:
        return
    for modelo in apps.get_app_config('core').get_models():
        campos = {campo.name for campo in modelo._meta.get_fields()}
        if 'organizacao' in campos and modelo._meta.model_name != 'vinculo':
            modelo._base_manager.filter(organizacao__isnull=True).update(organizacao=org)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0074_organizacao_em_todos_os_dados'),
    ]

    operations = [
        migrations.RunPython(preencher_organizacao, migrations.RunPython.noop),
    ]
