from django.db import migrations, models


def seed_almoxarifado(apps, schema_editor):
    Andar = apps.get_model('core', 'Andar')
    Comodo = apps.get_model('core', 'Comodo')
    LocalArmazenamento = apps.get_model('core', 'LocalArmazenamento')

    estrutura = [
        ('2º Andar', 'Quarto-Dividido-2° andar', ['Área Comum', 'Mala de Ferramenta']),
        ('Térreo', 'Garagem', ['Área Comum', 'Armário de Metal']),
        ('Térreo', 'Lavanderia', ['Área Comum', 'Prateleira de Metal']),
        ('Térreo', 'Cozinha', ['Área Comum', 'Armário Utensílios', 'Armário Despesa']),
        ('Térreo', 'Sala da Cozinha', ['Área Comum', 'Armário Potes', 'Armário Vidro']),
        ('Térreo', 'Sala dos Quadrinhos', ['Área Comum', 'Mesa de Cabeceira']),
        ('3º Andar', 'Terceiro Andar', ['Área Comum', 'Armário Branco', 'Armário Vermelho']),
        ('Térreo', 'Varanda', ['Área Comum']),
        ('1º Andar', 'Primeiro Andar', ['Área Comum', 'Sala e cozinha']),
        ('2º Andar', 'Quarto Suíte 2°Andar', ['Área Comum', 'Guarda roupa', 'Mesa']),
        ('2º Andar', 'Quarto Individual Cazares 2°Andar', ['Área Comum', 'Guarda roupa', 'Armário', 'Mesa']),
        ('2º Andar', 'Quarto Individual Milhouse 2°Andar', ['Área Comum', 'Guarda roupa', 'Armário', 'Mesa de Cabeceira', 'Mesa']),
        ('3º Andar', 'Quarto Individual Mary Kay 3° Andar', ['Área Comum', 'Guarda roupa', 'Mesa de Cabeceira', 'Mesa']),
        ('3º Andar', 'Quarto Individual Tayzmanias 3°Andar', ['Área Comum', 'Arara', 'Armário', 'Mesa']),
        ('3º Andar', 'Quarto Dividido 3° Andar', ['Área Comum', 'Guarda roupa', 'Armário', 'Mesa']),
        ('3º Andar', 'Quarto Individual Mibs 3° Andar', ['Área Comum', 'Guarda roupa', 'Mesa de Cabeceira', 'Mesa']),
        ('3º Andar', 'Quarto Individual Panda 3°Andar', ['Área Comum', 'Guarda roupa', 'Armário', 'Mesa']),
        ('Térreo', 'Quarto Individual Moedas', ['Área Comum', 'Guarda roupa', 'Armário', 'Mesa']),
        ('Térreo', 'Quarto Individual Casimiro', ['Área Comum', 'Guarda roupa', 'Mesa de Cabeceira', 'Mesa']),
        ('1º Andar', 'Banheiro 1° Andar', ['Área Comum']),
        ('2º Andar', 'Banheiro 2° Andar', ['Área Comum']),
        ('2º Andar', 'Banheiro Suíte 2° Andar', ['Área Comum']),
        ('3º Andar', 'Banheiro 3° Andar', ['Área Comum', 'Espelho/Armário']),
        ('Térreo', 'Quintal', ['Área Comum']),
    ]

    andares = {}
    comodos = {}
    for andar_nome, comodo_nome, locais in estrutura:
        andar = andares.get(andar_nome)
        if not andar:
            andar, _ = Andar.objects.get_or_create(nome=andar_nome)
            andares[andar_nome] = andar
        comodo_key = (andar_nome, comodo_nome)
        if comodo_key not in comodos:
            comodo, _ = Comodo.objects.get_or_create(nome=comodo_nome, andar=andar)
            comodos[comodo_key] = comodo
        comodo = comodos[comodo_key]
        for local_nome in locais:
            LocalArmazenamento.objects.get_or_create(nome=local_nome, comodo=comodo)

    fallback_andar, _ = Andar.objects.get_or_create(nome='Térreo')
    fallback_comodo, _ = Comodo.objects.get_or_create(nome='Sem Cômodo', andar=fallback_andar)

    local_para_comodo = {}
    comodo_por_nome = {c.nome: c for c in Comodo.objects.all()}
    for andar_nome, comodo_nome, locais in estrutura:
        comodo = comodos[(andar_nome, comodo_nome)]
        for local_nome in locais:
            local_para_comodo.setdefault(local_nome, comodo)

    for local in LocalArmazenamento.objects.filter(comodo__isnull=True):
        if local.nome in local_para_comodo:
            local.comodo = local_para_comodo[local.nome]
        elif local.nome in comodo_por_nome:
            local.comodo = comodo_por_nome[local.nome]
        else:
            local.comodo = fallback_comodo
        local.save(update_fields=['comodo'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_notafiscal_flags'),
    ]

    operations = [
        migrations.CreateModel(
            name='Andar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='Comodo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=150)),
                ('andar', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='comodos', to='core.andar')),
            ],
            options={
                'ordering': ['andar__nome', 'nome'],
                'unique_together': {('nome', 'andar')},
            },
        ),
        migrations.AddField(
            model_name='localarmazenamento',
            name='comodo',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='locais', to='core.comodo'),
        ),
        migrations.RunPython(seed_almoxarifado, migrations.RunPython.noop),
    ]
