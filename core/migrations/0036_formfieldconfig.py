from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_andar_comodo_local'),
    ]

    operations = [
        migrations.CreateModel(
            name='FormFieldConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('form_key', models.CharField(max_length=100)),
                ('field_name', models.CharField(max_length=100)),
                ('label', models.CharField(blank=True, max_length=200)),
                ('visible', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['form_key', 'order', 'field_name'],
                'unique_together': {('form_key', 'field_name')},
            },
        ),
    ]
