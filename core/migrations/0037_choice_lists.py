from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_formfieldconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChoiceList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100, unique=True)),
                ('label', models.CharField(max_length=200)),
            ],
            options={
                'ordering': ['label', 'key'],
            },
        ),
        migrations.CreateModel(
            name='ChoiceOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=100)),
                ('label', models.CharField(max_length=200)),
                ('order', models.PositiveIntegerField(default=0)),
                ('active', models.BooleanField(default=True)),
                ('choice_list', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='core.choicelist')),
            ],
            options={
                'ordering': ['order', 'label'],
                'unique_together': {('choice_list', 'value')},
            },
        ),
    ]
