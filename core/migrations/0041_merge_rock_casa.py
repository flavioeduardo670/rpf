from django.db import migrations


def merge_rock_to_casa(apps, schema_editor):
    Morador = apps.get_model('core', 'Morador')
    ConsumoEstoque = apps.get_model('core', 'ConsumoEstoque')

    casa = Morador.objects.filter(nome='Casa').first()
    rock = Morador.objects.filter(nome='Rock').first()

    if rock and casa:
        ConsumoEstoque.objects.filter(morador=rock).update(morador=casa)
        rock.delete()
        return

    if rock and not casa:
        rock.nome = 'Casa'
        rock.apelido = 'Casa'
        rock.ativo = False
        rock.save(update_fields=['nome', 'apelido', 'ativo'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_rockitem_consumo'),
    ]

    operations = [
        migrations.RunPython(merge_rock_to_casa, noop),
    ]
