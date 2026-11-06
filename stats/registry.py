"""
    Desc: Registry of dialect(s), a dialect is registered by its name
    Creator: Kirosha
"""

from typing import Callable

_DIALECTS: dict[str, type] = {}

def register(name: str) -> Callable[[type], type]:
    def decorator(dialect: type) -> type:
        _DIALECTS[name] = dialect
        return dialect
    return decorator

def available_dialects() -> list[str]:
    return sorted(_DIALECTS)

def get_dialect(name: str) -> type:
    dialect = _DIALECTS.get(name)
    if not dialect: raise SystemExit(f"Неизвестная СУБД: {name}. Доступные: {', '.join(available_dialects())}")
    return dialect
