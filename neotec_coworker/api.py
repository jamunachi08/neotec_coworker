# Copyright (c) 2026, Neotec Integrated Solutions
# License: Proprietary
"""Endpoints used by the chat page, the setup wizard and the form buttons."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

import neotec_coworker
from neotec_coworker.engine import gateway, runner

USE_ROLES = {"Coworker User", "Coworker Admin", "System Manager"}
ADMIN_ROLES = {"Coworker Admin", "System Manager"}

PRESETS = {
    "Google Gemini": {"provider_type": "OpenAI Compatible",
                      "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                      "model": "gemini-3.8-flash", "data_location": "External", "needs_key": 1},
    "OpenAI": {"provider_type": "OpenAI Compatible", "base_url": "https://api.openai.com/v1", "model": "",
               "data_location": "External", "needs_key": 1},
    "Anthropic Claude": {"provider_type": "Anthropic", "base_url": "https://api.anthropic.com",
                         "model": "claude-sonnet-5-5", "data_location": "External", "needs_key": 1},
    "Azure OpenAI": {"provider_type": "Azure OpenAI",
                     "base_url": "https://YOUR-RESOURCE.openai.azure.com/openai/deployments/YOUR-DEPLOYMENT",
                     "model": "YOUR-DEPLOYMENT", "data_location": "External", "needs_key": 1,
                     "api_version": "2024-10-21"},
    "On-Premises (Ollama / vLLM)": {"provider_type": "OpenAI Compatible", "base_url": "http://YOUR-SERVER:11434/v1",
                                    "model": "", "data_location": "On-Premises", "needs_key": 0},
    "NeotecAI On-Premises": {"provider_type": "OpenAI Compatible", "base_url": "https://YOUR-NEOTECAI-HOST/v1",
                             "model": "", "data_location": "On-Premises", "needs_key": 0},
}


def _roles():
    return set(frappe.get_roles())


def _require_use():
    if not _roles() & USE_ROLES:
        frappe.throw(_("Ask your administrator for the Coworker User role."), frappe.PermissionError)


def _require_admin():
    if not _roles() & ADMIN_ROLES:
        frappe.throw(_("Only a Coworker Admin can do this."), frappe.PermissionError)


def _own(conv_name):
    conv = frappe.get_doc("Coworker Conversation", conv_name)
    if conv.user != frappe.session.user and not _roles() & ADMIN_ROLES:
        frappe.throw(_("This conversation belongs to someone else."), frappe.PermissionError)
    return conv


# ---------------------------------------------------------------- chat

@frappe.whitelist()
def bootstrap():
    _require_use()
    s = gateway.settings()
    coworkers = []
    for name in frappe.get_all("AI Coworker", filters={"enabled": 1, "chat_visible": 1}, pluck="name",
                               order_by="creation asc"):
        cw = frappe.get_doc("AI Coworker", name)
        if not runner.can_use(cw):
            continue
        coworkers.append({
            "name": cw.name, "title": cw.title, "title_ar": cw.title_ar, "icon": cw.icon or "🤖",
            "color": cw.color, "description": cw.description, "description_ar": cw.description_ar,
            "starters": [p.strip() for p in (cw.starter_prompts or "").splitlines() if p.strip()][:6],
        })
    return {
        "version": neotec_coworker.__version__,
        "enabled": cint(s.enabled), "setup_completed": cint(s.setup_completed),
        "is_admin": int(bool(_roles() & ADMIN_ROLES)),
        "coworkers": coworkers,
        "conversations": list_conversations(),
        "pending_approvals": frappe.db.count("Coworker Approval", {"status": "Pending"})
        if _roles() & ({"Coworker Approver"} | ADMIN_ROLES) else 0,
    }


@frappe.whitelist()
def list_conversations(limit=40):
    _require_use()
    return frappe.get_all("Coworker Conversation", filters={"user": frappe.session.user},
                          fields=["name", "title", "coworker", "status", "channel", "last_message_at", "modified"],
                          order_by="modified desc", limit_page_length=min(cint(limit) or 40, 200))


@frappe.whitelist()
def get_conversation(name):
    _require_use()
    conv = _own(name)
    labels = dict(frappe.get_all("Coworker Tool", fields=["name", "label"], as_list=True))
    msgs = frappe.get_all("Coworker Message", filters={"conversation": name},
                          fields=["name", "seq", "role", "content", "status", "tool_name", "tool_call_id",
                                  "tool_calls", "blocks", "approval", "creation"],
                          order_by="seq asc", limit_page_length=500)
    approvals = {}
    for m in msgs:
        if m.tool_calls:
            m.tool_calls = json.loads(m.tool_calls)
            for c in m.tool_calls:
                c["label"] = labels.get(c["name"], c["name"])
        if m.blocks:
            m.blocks = json.loads(m.blocks)
        if m.role == "tool":
            m.tool_label = labels.get(m.tool_name, m.tool_name)
            try:
                payload = json.loads(m.content or "{}")
                m.note = payload.get("message") if isinstance(payload, dict) else None
            except ValueError:
                m.note = None
            m.content = None  # raw tool output stays server side; the Activity panel shows the audit row
        if m.approval and m.approval not in approvals:
            a = frappe.get_doc("Coworker Approval", m.approval)
            ok, why = gateway.can_decide(a)
            approvals[m.approval] = {"name": a.name, "status": a.status, "summary": a.summary,
                                     "approver_role": a.approver_role, "requested_by": a.requested_by,
                                     "decided_by": a.decided_by, "comment": a.decision_comment,
                                     "arguments": a.arguments, "can_decide": ok, "why_not": why}
    stale = (conv.status in ("Running", "Stopping")
             and get_datetime(conv.modified) < add_to_date(now_datetime(), minutes=-20))
    return {"name": conv.name, "title": conv.title, "coworker": conv.coworker, "status": conv.status,
            "stale": stale, "context_doctype": conv.context_doctype, "context_name": conv.context_name,
            "channel": conv.channel, "messages": msgs, "approvals": approvals}


@frappe.whitelist()
def send_message(text, conversation=None, coworker=None, context_doctype=None, context_name=None):
    _require_use()
    text = (text or "").strip()
    if not text:
        frappe.throw(_("Type a message first."))
    if len(text) > 8000:
        frappe.throw(_("Messages are limited to 8,000 characters."))
    if conversation:
        conv = _own(conversation)
        if conv.status in ("Running", "Stopping", "Waiting Approval"):
            frappe.throw(_("The coworker is still working on this conversation."))
    else:
        if not coworker:
            frappe.throw(_("Choose a coworker."))
        cw = frappe.get_doc("AI Coworker", coworker)
        if not (cw.enabled and runner.can_use(cw)):
            frappe.throw(_("You do not have access to this coworker."), frappe.PermissionError)
        if context_doctype and context_name:
            frappe.get_doc(context_doctype, context_name).check_permission("read")
        conv = frappe.get_doc({
            "doctype": "Coworker Conversation", "coworker": coworker, "user": frappe.session.user,
            "title": text.splitlines()[0][:80], "status": "Idle",
            "channel": "Form" if context_doctype else "Chat",
            "context_doctype": context_doctype, "context_name": context_name,
        }).insert(ignore_permissions=True)
    runner.add_message(conv.name, "user", text, status="ok")
    runner.enqueue_turn(conv.name)
    return {"conversation": conv.name}


@frappe.whitelist()
def submit_form(conversation, title, values):
    vals = json.loads(values) if isinstance(values, str) else values
    lines = [f"- {k}: {v}" for k, v in (vals or {}).items()]
    return send_message(f"{title or 'Form'}:\n" + "\n".join(lines), conversation=conversation)


@frappe.whitelist()
def stop(conversation):
    _require_use()
    conv = _own(conversation)
    if conv.status == "Running":
        frappe.db.set_value("Coworker Conversation", conv.name, "status", "Stopping")
    elif conv.status in ("Stopping", "Error"):
        frappe.db.set_value("Coworker Conversation", conv.name, "status", "Idle")
    return {"ok": True}


@frappe.whitelist()
def reset(conversation):
    """Unsticks a conversation whose background job died (e.g. a worker restart)."""
    _require_use()
    conv = _own(conversation)
    for m in frappe.get_all("Coworker Message", filters={"conversation": conv.name, "status": "pending"},
                            fields=["name", "approval"]):
        status = frappe.db.get_value("Coworker Approval", m.approval, "status") if m.approval else None
        if status != "Pending":
            frappe.db.set_value("Coworker Message", m.name, "status", "expired")
    frappe.db.set_value("Coworker Conversation", conv.name, "status", "Idle")
    return {"ok": True}


@frappe.whitelist()
def decide_approval(approval, approve, comment=None):
    return gateway.decide(approval, bool(cint(approve)), comment or "")


@frappe.whitelist()
def get_activity(conversation):
    _require_use()
    _own(conversation)
    return frappe.get_all("Coworker Action Log", filters={"conversation": conversation},
                          fields=["name", "tool", "status", "decision", "is_write", "reason", "rule", "approval",
                                  "duration_ms", "error", "creation"],
                          order_by="creation desc", limit_page_length=200)


@frappe.whitelist()
def rename_conversation(conversation, title):
    _own(conversation)
    frappe.db.set_value("Coworker Conversation", conversation, "title", (title or "")[:80])
    return {"ok": True}


@frappe.whitelist()
def delete_conversation(conversation):
    conv = _own(conversation)
    frappe.db.delete("Coworker Message", {"conversation": conv.name})
    frappe.delete_doc("Coworker Conversation", conv.name, ignore_permissions=True)
    return {"ok": True}


# ---------------------------------------------------------------- setup wizard

@frappe.whitelist()
def get_setup_state():
    _require_admin()
    s = gateway.settings()
    return {
        "presets": PRESETS,
        "providers": frappe.get_all("Coworker Provider", fields=["name", "preset", "provider_type", "model",
                                                                 "data_location", "is_default", "enabled", "last_test"]),
        "coworkers": frappe.get_all("AI Coworker", fields=["name", "title", "title_ar", "icon", "enabled",
                                                           "chat_visible", "description"], order_by="creation asc"),
        "settings": {k: s.get(k) for k in ("enabled", "residency_mode", "redact_external", "allow_self_approval",
                                           "mcp_enabled", "default_provider", "setup_completed", "show_form_button")},
        "health": health(),
        "mcp_url": frappe.utils.get_url("/api/method/neotec_coworker.mcp.server.handle"),
    }


@frappe.whitelist()
def save_provider(preset, model, base_url=None, api_key=None, data_location=None, api_version=None,
                  provider_name=None):
    _require_admin()
    p = PRESETS.get(preset, {})
    name = provider_name or preset
    if frappe.db.exists("Coworker Provider", name):
        doc = frappe.get_doc("Coworker Provider", name)
    else:
        doc = frappe.new_doc("Coworker Provider")
        doc.provider_name = name
    doc.preset = preset if preset in PRESETS else "Custom"
    doc.provider_type = p.get("provider_type") or doc.provider_type or "OpenAI Compatible"
    doc.base_url = (base_url or p.get("base_url") or "").strip()
    doc.model = (model or p.get("model") or "").strip()
    doc.data_location = data_location or p.get("data_location") or "External"
    if api_version or p.get("api_version"):
        doc.api_version = api_version or p.get("api_version")
    if api_key:
        doc.api_key = api_key.strip()
    doc.enabled = 1
    doc.is_default = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return test_provider(doc.name)


@frappe.whitelist()
def test_provider(name):
    _require_admin()
    from neotec_coworker.engine import llm

    doc = frappe.get_doc("Coworker Provider", name)
    try:
        msg = llm.test_connection(doc)
        ok = True
    except Exception as e:  # noqa: BLE001
        msg, ok = f"Failed: {str(e)[:500]}", False
    doc.db_set("last_test", f"{now_datetime():%Y-%m-%d %H:%M} {msg}")
    return {"ok": ok, "message": msg, "provider": doc.name}


@frappe.whitelist()
def save_setup(coworkers=None, residency_mode=None, redact_external=None, allow_self_approval=None,
               mcp_enabled=None, grant_scope=None):
    _require_admin()
    enabled = set(json.loads(coworkers)) if isinstance(coworkers, str) else set(coworkers or [])
    if coworkers is not None:
        for row in frappe.get_all("AI Coworker", fields=["name", "chat_visible"]):
            if row.chat_visible:
                frappe.db.set_value("AI Coworker", row.name, "enabled", 1 if row.name in enabled else 0)
    s = frappe.get_single("Coworker Settings")
    if residency_mode in ("Guarded", "Strict", "Open"):
        s.residency_mode = residency_mode
    for field, val in (("redact_external", redact_external), ("allow_self_approval", allow_self_approval),
                       ("mcp_enabled", mcp_enabled)):
        if val is not None:
            s.set(field, cint(val))
    if not s.default_provider:
        s.default_provider = frappe.db.get_value("Coworker Provider", {"is_default": 1}, "name")
    s.setup_completed = 1
    s.save(ignore_permissions=True)
    granted = grant_access(grant_scope) if grant_scope in ("all", "me") else 0
    frappe.db.commit()
    return {"ok": True, "granted": granted}


def grant_access(scope):
    users = [frappe.session.user] if scope == "me" else frappe.get_all(
        "User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
        pluck="name", limit_page_length=1000)
    count = 0
    for user in users:
        if "Coworker User" in frappe.get_roles(user):
            continue
        frappe.get_doc("User", user).add_roles("Coworker User")
        count += 1
    return count


@frappe.whitelist()
def health():
    _require_admin()
    s = gateway.settings()
    checks = []

    def add(ok, label, fix=""):
        checks.append({"ok": bool(ok), "label": label, "fix": "" if ok else fix})

    add(s.enabled, "Coworkers are switched on", "Tick 'Enable Neotec Coworker' in Coworker Settings.")
    prov = s.default_provider or frappe.db.get_value("Coworker Provider", {"is_default": 1}, "name")
    add(prov, "An AI provider is configured", "Add a provider in step 1.")
    if prov:
        last = frappe.db.get_value("Coworker Provider", prov, "last_test") or ""
        add("Connected" in last, f"Provider {prov} answered its last test", "Run 'Test connection'.")
        loc = frappe.db.get_value("Coworker Provider", prov, "data_location")
        add(not (loc == "External" and s.residency_mode == "Strict"), "Provider location fits the residency mode",
            "Strict mode blocks external providers. Choose Guarded or an in-Kingdom provider.")
    try:
        from frappe.utils.scheduler import is_scheduler_disabled

        add(not is_scheduler_disabled(), "Scheduler is running (routines, expiries)",
            "Enable the scheduler (Frappe Cloud: Site > Settings, or bench enable-scheduler).")
    except Exception:  # noqa: BLE001
        pass
    try:
        from frappe.utils.background_jobs import get_workers

        add(len(get_workers()) > 0, "Background workers are running (coworkers answer in the background)",
            "Start workers. On Frappe Cloud they run automatically on paid plans.")
    except Exception:  # noqa: BLE001
        pass
    add(frappe.db.count("Coworker Tool", {"enabled": 1}) > 10, "Tools are registered", "Run bench migrate.")
    add(frappe.db.count("AI Coworker", {"enabled": 1, "chat_visible": 1}), "At least one coworker is enabled",
        "Enable coworkers in step 2.")
    users = frappe.db.count("Has Role", {"role": "Coworker User", "parenttype": "User"})
    add(users, f"{users} user(s) have the Coworker User role", "Grant access in step 3.")
    add(frappe.db.count("Coworker Policy Rule", {"enabled": 1}), "Policy rules are active",
        "Run bench migrate to load the starter policy pack.")
    return checks
