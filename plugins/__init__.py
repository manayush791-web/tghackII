"""
Plugin System
"""
import os
import sys
import importlib.util
import inspect

_HOOKS = {}

def register_hook(name):
    def decorator(func):
        if not inspect.iscoroutinefunction(func):
            raise ValueError(f"Hook {func.__name__} must be async")
        _HOOKS.setdefault(name, []).append(func)
        return func
    return decorator

async def call_hook(name, *args, **kwargs):
    results = []
    for handler in _HOOKS.get(name, []):
        try:
            results.append(await handler(*args, **kwargs))
        except Exception as e:
            print(f"[Plugin Error] {name}: {e}")
    return results

def load_plugins():
    d = os.path.dirname(os.path.abspath(__file__))
    for f in os.listdir(d):
        if f.startswith("_") or not f.endswith(".py"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"plugins.{f[:-3]}", os.path.join(d, f))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"plugins.{f[:-3]}"] = mod
            spec.loader.exec_module(mod)
            print(f"🔌 Plugin loaded: {f}")
        except Exception as e:
            print(f"[Plugin Error] {f}: {e}")

def get_loaded_plugins():
    return list(set(h.__module__.replace("plugins.", "") for hooks in _HOOKS.values() for h in hooks))
