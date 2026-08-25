import pandas as pd
import streamlit as st
from pathlib import Path
from dataclasses import fields
from collections import defaultdict

from extraction.cache import CacheEntry

test_path1 = Path("uv.lock")
CacheEntry(
    hash_key=CacheEntry.get_hash_key(test_path1), name="Flo", company="BYOH"
).save()
test_path2 = Path("pyproject.toml")
CacheEntry(
    hash_key=CacheEntry.get_hash_key(test_path2), name="Aaron", company="BYOH"
).save()


def get_cache_entries():
    return CacheEntry.all_entries()


def render_dataframe(cache_entries: list[CacheEntry]) -> pd.DataFrame:
    columns = [f.name for f in fields(CacheEntry)]

    if not cache_entries:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame([entry.__dict__ for entry in cache_entries])

    return df.reindex(columns=columns).fillna("")


cache_entries = get_cache_entries()

st.table(render_dataframe(cache_entries)[["name", "company"]])
