# Generated by Django 3.0.3 on 2020-05-16 22:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('course', '0005_auto_20200516_1515'),
    ]

    operations = [
        migrations.AddField(
            model_name='questioncategory',
            name='parent',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='course.QuestionCategory'),
        ),
    ]