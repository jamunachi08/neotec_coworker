# Copyright (c) 2026, Neotec Integrated Solutions
# License: Proprietary
"""Tool registry.

Three sources feed one registry:
  * Built-in tools, declared with the ``@tool`` decorator in ``neotec_coworker.tools.*``.
  * Extension tools from other apps, through the ``neotec_coworker_tools`` hook
    (a dotted path to a function returning a list of tool dicts).
  * Tools discovered on external MCP servers (``Coworker MCP Server``).

The registry never decides whether a tool may run; the gateway does.
"""

from __future__ import annotations

import importlib

_BUILTIN: dict[str, dict] = {}
_LOADED = False

BUILTIN_MODULES = (
    "neotec_coworker.tools.data",
    "neotec_coworker.tools.finance",
    "neotec_coworker.tools.stock",
    "neotec_coworker.tools.ksa",
    "neotec_coworker.tools.knowledge",
    "neotec_coworker.tools.memory",
    "neotec_coworker.tools.ui",
    "neotec_coworker.tools.actions",
)

CATEGORIES = {
    "Data", "Finance", "Stock", "KSA Compliance", "Knowledge", "Memory",
    "Interface", "Actions", "External (MCP)", "Extension",
}


def tool(name, label, description, parameters=None, category="Data", is_write=False, risk="Low"):
    """Declare a built-in tool. ``parameters`` is a JSON-schema ``properties`` dict plus optional ``required``."""

    def deco(fn):
        params = dict(parameters or {})
        required = params.pop("__required__", [])
        _BUILTIN[name] = {
            "name": name,
            "label": label,
            "description": description,
            "schema": {"type": "object", "properties": params, "required": required},
            "category": category if category in CATEGORIES else "Extension",
            "is_write": bool(is_write),
            "risk": risk,
            "source": "Built-in",
            "fn": fn,
        }
        return fn

    return deco


def _load_builtin():
    global _LOADED
    if _LOADED:
        return
    for mod in BUILTIN_MODULES:
        importlib.import_module(mod)
    _LOADED = True


def builtin_tools() -> dict[str, dict]:
    _load_builtin()
    return dict(_BUILTIN)


def extension_tools() -> dict[str, dict]:
    import frappe

    out = {}
    for path in frappe.get_hooks("neotec_coworker_tools") or []:
        try:
            for spec in frappe.get_attr(path)() or []:
                name = spec.get("name")
                fn = spec.get("fn")
                if not name or not fn:
                    continue
                if isinstance(fn, str):
                    fn = frappe.get_attr(fn)
                props = dict(spec.get("parameters") or {})
                required = props.pop("__required__", spec.get("required") or [])
                out[name] = {
                    "name": name,
                    "label": spec.get("label") or name,
                    "description": spec.get("description") or "",
                    "schema": {"type": "object", "properties": props, "required": required},
                    "category": "Extension",
                    "is_write": bool(spec.get("is_write", True)),
                    "risk": spec.get("risk", "Medium"),
                    "source": "Extension",
                    "fn": fn,
                }
        except Exception:
            frappe.log_error(title="Neotec Coworker: extension tool hook failed", message=path)
    return out


def mcp_tools() -> dict[str, dict]:
    import frappe

    from neotec_coworker.mcp import client

    out = {}
    if not frappe.db.table_exists("Coworker MCP Server"):
        return out
    for row in frappe.get_all("Coworker MCP Server", filters={"enabled": 1},
                              fields=["name", "tools_cache", "read_only_tools"]):
        out.update(client.registry_entries(row))
    return out


def all_tools() -> dict[str, dict]:
    tools = builtin_tools()
    tools.update(extension_tools())
    tools.update(mcp_tools())
    return tools


def get_tool(name: str) -> dict | None:
    _load_builtin()
    if name in _BUILTIN:
        return _BUILTIN[name]
    if name.startswith("mcp_"):
        return mcp_tools().get(name)
    return extension_tools().get(name)
