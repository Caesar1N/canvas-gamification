# Generated by Django 3.0.7 on 2020-08-07 19:52

import course.models.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course', '0004_auto_20200731_2057'),
    ]

    operations = [
        migrations.AddField(
            model_name='userquestionjunction',
            name='random_seed',
            field=models.IntegerField(default=course.models.models.random_seed),
        ),
    ]