from django.db import migrations, models


def _colunas(schema_editor, tabela):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, tabela)
        }


def adicionar_coluna_nome(apps, schema_editor):
    """Adiciona core_ataparticipante.nome somente se ainda não existir.

    A versão anterior desta migração usava ``ADD COLUMN IF NOT EXISTS``, que é
    exclusivo do PostgreSQL e quebrava o SQLite (inclusive o banco de testes).
    Esta versão é idempotente e portátil entre bancos.
    """
    AtaParticipante = apps.get_model('core', 'AtaParticipante')
    tabela = AtaParticipante._meta.db_table
    if 'nome' in _colunas(schema_editor, tabela):
        return
    campo = models.CharField(blank=True, default='', max_length=150)
    campo.set_attributes_from_name('nome')
    campo.model = AtaParticipante
    schema_editor.add_field(AtaParticipante, campo)


def remover_coluna_nome(apps, schema_editor):
    AtaParticipante = apps.get_model('core', 'AtaParticipante')
    tabela = AtaParticipante._meta.db_table
    if 'nome' not in _colunas(schema_editor, tabela):
        return
    schema_editor.execute(
        f'ALTER TABLE {schema_editor.quote_name(tabela)} DROP COLUMN {schema_editor.quote_name("nome")}'
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0056_atareuniao_registro_e_5w2h"),
        ("core", "0056_ataparticipante_atatopico"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(adicionar_coluna_nome, remover_coluna_nome),
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
