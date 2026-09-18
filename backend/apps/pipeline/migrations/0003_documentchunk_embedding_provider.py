from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pipeline", "0002_documentchunk_embedding_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentchunk",
            name="embedding_provider",
            field=models.CharField(default="legacy", max_length=32),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="documentchunk",
            name="embedding_provider",
            field=models.CharField(default="mock", max_length=32),
        ),
    ]
