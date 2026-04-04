from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_merge_rock_casa'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventoCalendario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200)),
                ('data', models.DateField()),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-data', 'titulo'],
            },
        ),
    ]
