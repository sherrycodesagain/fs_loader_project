import os
import importlib

def auto_import_charts():
    base_dir = os.path.dirname(__file__)
    base_module = "services.charts"

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                rel_path = os.path.relpath(os.path.join(root, file), start=base_dir)
                module_path = rel_path.replace(os.sep, ".").replace(".py", "")
                full_module_path = f"{base_module}.{module_path}"
                importlib.import_module(full_module_path)

auto_import_charts()
