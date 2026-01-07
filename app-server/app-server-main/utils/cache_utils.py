from cache.memory_store import get_filter_from_cache, set_filter_cache
import hashlib

def generate_cache_key(prefix, dataset_id, chart_name, period_type=None, selected_period=None, filter_hash=None):
    base = f"{dataset_id}|{chart_name}|{period_type or ''}|{selected_period or ''}|{filter_hash or ''}"
    hash_key = hashlib.sha256(base.encode()).hexdigest()
    return f"{prefix}::{hash_key}"

def get_or_set_cache(dataset_id, cache_key, compute_fn):
    cached = get_filter_from_cache(dataset_id, cache_key)
    if cached is not None:
        print(f"🧠 Cache HIT → {cache_key}")
        return cached

    print(f"🆕 Cache MISS → {cache_key}")
    result = compute_fn()
    set_filter_cache(dataset_id, cache_key, result)
    return result
