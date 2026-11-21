"""Reconcilia o histórico de migrações com o models.py atual.

Durante os merges das funcionalidades de atas (PRs paralelos de 14/04/2026),
o models.py passou a usar ``AtaTopico.texto`` e deixou de usar
``titulo_assunto``, ``desenvolvimento``, ``AtaParticipante.assinatura_status``
e o modelo ``AtaAcao5W2H``, mas nenhuma migração refletia isso. Em bancos
criados só pelas migrações (testes, homologação, novas instalações) a
gravação de tópicos e participantes da ata quebrava.

Como o banco de produção pode ter sido ajustado manualmente (ver 0057), a
parte de banco desta migração é idempotente: verifica o que existe antes de
alterar. Os dados de ``titulo_assunto``/``desenvolvimento`` são copiados para
``texto`` no mesmo formato que o formulário grava ("assunto\\n- desenvolvimento").

A tabela legada ``core_ataacao5w2h`` é apenas removida do estado do Django;
ela permanece no banco para não apagar dados antigos sem revisão humana.
"""
import django.db.models.deletion
from django.db import migrations, models


def _colunas(schema_editor, tabela):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, tabela)
        }


def _constraints(schema_editor, tabela):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, tabela)


def reconciliar_banco(apps, schema_editor):
    qn = schema_editor.quote_name
    AtaTopico = apps.get_model('core', 'AtaTopico')
    tabela_topico = AtaTopico._meta.db_table
    tabela_participante = apps.get_model('core', 'AtaParticipante')._meta.db_table

    # 1) Remove a restrição única (ata, ordem), se existir. Feito antes das
    #    mudanças de coluna porque no SQLite isso recria a tabela a partir do
    #    modelo histórico.
    if 'unique_ata_topico_ordem' in _constraints(schema_editor, tabela_topico):
        constraint = next(
            c for c in AtaTopico._meta.constraints if c.name == 'unique_ata_topico_ordem'
        )
        schema_editor.remove_constraint(AtaTopico, constraint)

    # 2) Garante a coluna "texto".
    colunas_topico = _colunas(schema_editor, tabela_topico)
    if 'texto' not in colunas_topico:
        schema_editor.execute(
            f"ALTER TABLE {qn(tabela_topico)} ADD COLUMN {qn('texto')} text NOT NULL DEFAULT ''"
        )

    # 3) Migra o conteúdo antigo para "texto" sem sobrescrever o que já existe.
    if {'titulo_assunto', 'desenvolvimento'} <= colunas_topico:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT id, {qn('titulo_assunto')}, {qn('desenvolvimento')}, {qn('texto')} "
                f"FROM {qn(tabela_topico)}"
                if 'texto' in colunas_topico
                else f"SELECT id, {qn('titulo_assunto')}, {qn('desenvolvimento')}, '' FROM {qn(tabela_topico)}"
            )
            linhas = cursor.fetchall()
        for pk, titulo, desenvolvimento, texto in linhas:
            if (texto or '').strip():
                continue
            titulo = (titulo or '').strip()
            desenvolvimento = (desenvolvimento or '').strip()
            novo = f"{titulo}\n- {desenvolvimento}" if titulo and desenvolvimento else (titulo or desenvolvimento)
            schema_editor.execute(
                f"UPDATE {qn(tabela_topico)} SET {qn('texto')} = %s WHERE id = %s",
                [novo, pk],
            )

    # 4) Remove colunas que o código não usa mais.
    for coluna in ('titulo_assunto', 'desenvolvimento'):
        if coluna in _colunas(schema_editor, tabela_topico):
            schema_editor.execute(f"ALTER TABLE {qn(tabela_topico)} DROP COLUMN {qn(coluna)}")
    if 'assinatura_status' in _colunas(schema_editor, tabela_participante):
        schema_editor.execute(
            f"ALTER TABLE {qn(tabela_participante)} DROP COLUMN {qn('assinatura_status')}"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_cobrancaaluguel_mercadopago'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # Participante sem morador vinculado passa a ser permitido.
                migrations.AlterField(
                    model_name='ataparticipante',
                    name='morador',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.morador'),
                ),
                migrations.RenameIndex(
                    model_name='contafixamensal',
                    new_name='core_contaf_mes_ref_a4c365_idx',
                    old_name='core_contaf_mes_ref_1ea7f2_idx',
                ),
                migrations.RunPython(reconciliar_banco),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name='ataacao5w2h',
                    name='ata_reuniao',
                ),
                migrations.RemoveField(
                    model_name='ataacao5w2h',
                    name='ordem_servico',
                ),
                migrations.AlterModelOptions(
                    name='ataparticipante',
                    options={'ordering': ['nome']},
                ),
                migrations.RemoveConstraint(
                    model_name='atatopico',
                    name='unique_ata_topico_ordem',
                ),
                migrations.RenameIndex(
                    model_name='contafixamensal',
                    new_name='core_contaf_mes_ref_a4c365_idx',
                    old_name='core_contaf_mes_ref_1ea7f2_idx',
                ),
                migrations.RemoveField(
                    model_name='ataparticipante',
                    name='assinatura_status',
                ),
                migrations.RemoveField(
                    model_name='atatopico',
                    name='desenvolvimento',
                ),
                migrations.RemoveField(
                    model_name='atatopico',
                    name='titulo_assunto',
                ),
                migrations.AddField(
                    model_name='atatopico',
                    name='texto',
                    field=models.TextField(default=''),
                    preserve_default=False,
                ),
                migrations.AlterField(
                    model_name='ataparticipante',
                    name='morador',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.morador'),
                ),
                migrations.AlterField(
                    model_name='atatopico',
                    name='ordem',
                    field=models.PositiveIntegerField(default=1),
                ),
                migrations.AlterField(
                    model_name='comodo',
                    name='nome',
                    field=models.CharField(blank=True, default='', max_length=150),
                ),
                migrations.AlterField(
                    model_name='ordemservico',
                    name='status',
                    field=models.CharField(choices=[('aberta', 'Aberta'), ('andamento', 'Em andamento'), ('aguardando_orcamento', 'Aguardando orçamento'), ('nao_atendida', 'Não atendida'), ('finalizada', 'Finalizada')], default='aberta', max_length=20),
                ),
                migrations.DeleteModel(
                    name='AtaAcao5W2H',
                ),
            ],
        ),
    ]
