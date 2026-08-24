import os
import json
from pathlib import Path
from uuid import uuid4, UUID
from dataclasses import dataclass, field


CACHE_PATH = Path(".cache")


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return str(obj)
        return json.JSONEncoder.default(self, obj)


@dataclass(frozen=True, kw_only=True)
class CacheEntry:
    id: UUID = field(default=uuid4())
    name: str
    company: str

    def save(self):
        with open(os.path.join(CACHE_PATH, f"{self.id}"), "w+") as f:
            json.dump(self.__dict__, f, cls=UUIDEncoder)

    @classmethod
    def load(cls, cache_id: str) -> "CacheEntry":
        with open(os.path.join(CACHE_PATH, f"{cache_id}"), "r") as f:
            file = json.load(f)
        return cls(**file)

    @classmethod
    def remove(cls, cache_id: str):
        os.remove(os.path.join(CACHE_PATH, f"{cache_id}"))
