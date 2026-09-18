# Generated manually for the provider-isolated test/offline default.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pipeline", "0003_documentchunk_embedding_provider"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documentchunk",
            name="embedding_model_name",
            field=models.CharField(max_length=64, default="mock-embedding-v1"),
        ),
        migrations.AlterField(
            model_name="documentchunk",
            name="preprocessing_fingerprint",
            field=models.CharField(
                max_length=64, default="v2-pdf-layout-ocr-sentence"
            ),
        ),
    ]
