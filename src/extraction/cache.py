import json
import hashlib
from pathlib import Path
from dataclasses import dataclass


CACHE_PATH = Path(__file__).parent / ".cache"


@dataclass(frozen=True, kw_only=True)
class CacheEntry:
    hash_key: str
    name: str
    company: str

    @staticmethod
    def get_hash_key(image_path: Path):
        return hashlib.sha256(image_path.read_bytes()).hexdigest()[:16]

    @property
    def path(self) -> Path:
        return CACHE_PATH / f"{self.hash_key}"

    def save(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.__dict__)
        try:
            with self.path.open("x", encoding="utf-8") as f:
                f.write(payload)
            return True
        except FileExistsError:
            return False

    @classmethod
    def load(cls, hash_key: str) -> "CacheEntry | None":
        target = CACHE_PATH / f"{hash_key}"
        if not target.exists():
            return None
        data = json.loads(target.read_text(encoding="utf-8"))
        return cls(**data)

    @classmethod
    def remove(cls, hash_key: str) -> bool:
        target = CACHE_PATH / f"{hash_key}"
        target.unlink(missing_ok=True)
        return not target.exists()

    @classmethod
    def all_entries(cls) -> list["CacheEntry"]:
        if not CACHE_PATH.exists():
            return []

        cache_entries = []
        for path in sorted(CACHE_PATH.glob("*")):
            cache_entries.append(cls.load(path.stem))

        return cache_entries
