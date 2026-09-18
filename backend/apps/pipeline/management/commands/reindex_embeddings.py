import time

from django.core.management.base import BaseCommand, CommandError

from apps.intelligence.embeddings import get_embedding_adapter, get_embedding_metadata
from apps.pipeline.models import DocumentChunk
from apps.pipeline.reindex import reindex_tenders, rollback_tender
from apps.tenders.models import Tender


class Command(BaseCommand):
    help = "Reindexa o corpus selecionado com staging e promoção atômica."

    def add_arguments(self, parser):
        parser.add_argument("--tender-id", help="Reindexa somente este edital.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valida provider e relata o plano sem ler PDFs ou gerar embeddings.",
        )
        parser.add_argument(
            "--rollback-to-generation",
            type=int,
            help="Reativa uma geração anterior; exige --tender-id.",
        )

    def handle(self, *args, **options):
        started_at = time.monotonic()
        queryset = Tender.objects.filter(status="PROCESSED").order_by("created_at")
        tender_id = options.get("tender_id")
        if tender_id:
            queryset = queryset.filter(id=tender_id)
            if not queryset.exists():
                raise CommandError("Edital processado não encontrado.")

        rollback_generation = options.get("rollback_to_generation")
        if rollback_generation is not None:
            if not tender_id or options.get("dry_run"):
                raise CommandError(
                    "Rollback exige --tender-id e não pode ser combinado com --dry-run."
                )
            try:
                chunks = rollback_tender(queryset.get(), rollback_generation)
            except Exception as exc:
                raise CommandError("Rollback não realizado.") from exc
            self.stdout.write(
                self.style.SUCCESS(
                    f"rollback=promoted tender={tender_id} generation={rollback_generation} "
                    f"chunks={chunks}"
                )
            )
            return

        try:
            adapter = get_embedding_adapter()
            metadata = get_embedding_metadata(adapter)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        tenders = list(queryset)
        current_chunks = DocumentChunk.objects.filter(
            tender__in=tenders, is_current=True
        ).count()
        identity = (
            f"provider={metadata['provider']} model={metadata['model_name']} "
            f"version={metadata['model_version']} dimensions={metadata['dimensions']} "
            f"fingerprint={metadata['preprocessing_fingerprint']}"
        )
        self.stdout.write(
            self.style.NOTICE(
                f"plan tenders={len(tenders)} current_chunks={current_chunks} {identity}"
            )
        )
        if options.get("dry_run"):
            duration = time.monotonic() - started_at
            self.stdout.write(
                self.style.SUCCESS(
                    f"dry_run=ok tenders={len(tenders)} current_chunks={current_chunks} "
                    f"duration_seconds={duration:.2f}"
                )
            )
            return

        try:
            staged = reindex_tenders(tenders, adapter)
        except Exception as exc:
            duration = time.monotonic() - started_at
            self.stderr.write(
                self.style.ERROR(
                    f"reindex=rolled_back tenders={len(tenders)} "
                    f"duration_seconds={duration:.2f}"
                )
            )
            raise CommandError(
                "Reindexação não promovida; geração current preservada."
            ) from exc

        duration = time.monotonic() - started_at
        new_chunks = sum(item.staged_chunk_count for item in staged)
        self.stdout.write(
            self.style.SUCCESS(
                f"reindex=promoted tenders={len(staged)} old_chunks={current_chunks} "
                f"new_chunks={new_chunks} duration_seconds={duration:.2f}"
            )
        )
