import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RefreshTokenRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("family_id", models.UUIDField(db_index=True, default=uuid.uuid4)),
                ("jti", models.CharField(max_length=255, unique=True)),
                ("replaced_by_jti", models.CharField(blank=True, max_length=255, null=True)),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="refresh_token_records",
                        to="core.user",
                    ),
                ),
            ],
            options={
                "db_table": "core_refresh_token_record",
                "indexes": [
                    models.Index(
                        fields=["family_id", "revoked_at"],
                        name="refresh_family_revoked_idx",
                    ),
                ],
            },
        ),
    ]
