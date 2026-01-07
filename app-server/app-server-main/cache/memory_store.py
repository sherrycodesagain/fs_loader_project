"""
Global in-memory store for caching DataFrames, filters, and chart results.
This should be treated as ephemeral — cleared on app restart or replaced by Redis later.
"""

from threading import Lock

memory_store = {}
memory_lock = Lock()


def set_dataset(dataset_id, enriched_df, filters):
    with memory_lock:
        memory_store[dataset_id] = {
            "enriched_df": enriched_df,
            "filters": filters,
            "chart_cache": {},
            "filter_cache": {}
        }


def get_dataset(dataset_id):
    with memory_lock:
        return memory_store.get(dataset_id)


def get_dataframe(dataset_id):
    with memory_lock:
        return memory_store.get(dataset_id, {}).get("enriched_df")


def get_filters(dataset_id):
    with memory_lock:
        return memory_store.get(dataset_id, {}).get("filters")


def get_chart_cache(dataset_id):
    with memory_lock:
        return memory_store.get(dataset_id, {}).get("chart_cache", {})


def set_chart_cache(dataset_id, cache_key, chart_json):
    with memory_lock:
        if dataset_id not in memory_store:
            return
        if "chart_cache" not in memory_store[dataset_id]:
            memory_store[dataset_id]["chart_cache"] = {}
        memory_store[dataset_id]["chart_cache"][cache_key] = chart_json


def get_chart_from_cache(dataset_id, cache_key):
    with memory_lock:
        return memory_store.get(dataset_id, {}).get("chart_cache", {}).get(cache_key)

def get_filter_cache(dataset_id):
    with memory_lock:
        return memory_store.get(dataset_id, {}).get("filter_cache", {})


def get_filter_from_cache(dataset_id, cache_key):
    with memory_lock:
        return memory_store.get(dataset_id, {}).get("filter_cache", {}).get(cache_key)


def set_filter_cache(dataset_id, cache_key, result):
    with memory_lock:
        if dataset_id not in memory_store:
            return
        if "filter_cache" not in memory_store[dataset_id]:
            memory_store[dataset_id]["filter_cache"] = {}
        memory_store[dataset_id]["filter_cache"][cache_key] = result

def clear_filter_cache(dataset_id):
    with memory_lock:
        if dataset_id in memory_store and "filter_cache" in memory_store[dataset_id]:
            memory_store[dataset_id]["filter_cache"].clear()
