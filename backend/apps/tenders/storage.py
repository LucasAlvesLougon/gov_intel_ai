import os
from pathlib import Path

from django.conf import settings


class StorageAdapter:
    def save(self, company_id, tender_id, file_bytes: bytes) -> str:
        raise NotImplementedError

    def read_bytes(self, storage_key: str) -> bytes:
        raise NotImplementedError

    def exists(self, storage_key: str) -> bool:
        raise NotImplementedError

    def delete(self, storage_key: str) -> bool:
        raise NotImplementedError


class LocalStorageAdapter(StorageAdapter):
    def __init__(self, root_dir: str | None = None):
        if root_dir is None:
            root_dir = getattr(settings, "UPLOAD_ROOT", "/var/lib/govintel/uploads")
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, storage_key: str) -> Path:
        # Garante que a chave seja relativa e permaneça dentro do volume privado.
        if not isinstance(storage_key, str) or not storage_key or "\x00" in storage_key:
            raise ValueError("Chave de storage inválida.")
        candidate = Path(storage_key)
        if candidate.is_absolute():
            raise ValueError("Chave de storage inválida.")
        target = (self.root_dir / os.path.normpath(storage_key)).resolve()
        try:
            target.relative_to(self.root_dir)
        except ValueError as exc:
            raise ValueError("Chave de storage inválida.") from exc
        return target

    def save(self, company_id, tender_id, file_bytes: bytes) -> str:
        relative_key = f"{company_id}/{tender_id}.pdf"
        target_path = self._resolve_path(relative_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(file_bytes)
        return relative_key

    def read_bytes(self, storage_key: str) -> bytes:
        target_path = self._resolve_path(storage_key)
        if not target_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {storage_key}")
        return target_path.read_bytes()

    read = read_bytes

    def exists(self, storage_key: str) -> bool:
        return self._resolve_path(storage_key).is_file()

    def delete(self, storage_key: str) -> bool:
        target_path = self._resolve_path(storage_key)
        if target_path.exists():
            target_path.unlink()
            return True
        return False


_ADAPTER_INSTANCE = None


def get_storage_adapter() -> StorageAdapter:
    global _ADAPTER_INSTANCE
    if _ADAPTER_INSTANCE is None:
        _ADAPTER_INSTANCE = LocalStorageAdapter()
    return _ADAPTER_INSTANCE
