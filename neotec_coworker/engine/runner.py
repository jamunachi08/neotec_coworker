# Copyright (c) 2026, Neotec Integrated Solutions
# License: Proprietary
"""The agent loop. Runs in a background job (Frappe Cloud web requests time out; jobs do not).

    build context -> call model -> store reply -> for each tool call: gateway.execute -> store result
    -> repeat until the model answers without tools, an approval is pending, the step limit is hit,
       or the user presses Stop.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, nowdate

from neotec_coworker.engine import context, gateway, llm, redact, registry

EVENT = "neotec_coworker"
CHANNEL_INITIATOR = {"Chat": "Chat", "Form": "Form", "Routine": "Routine", "MCP": "MCP"}


class TurnError(Exception):
    """A problem the user (or admin) can act on; shown in the chat as is."""


# ---------------------------------------------------------------- helpers

def publish(conv_name, user, status, extra=None):
    frappe.publish_realtime(EVENT, {"conversation": conv_name, "status": status, **(extra or {})}, user=user)


def next_seq(conv_name) -> int:
    val = frappe.db.sql("select ifnull(max(seq), 0) from `tabCoworker Message` where conversation=%s", conv_name)
    return cint(val[0][0]) + 1


def add_message(conv_name, role, content="", **kw):
    doc = frappe.get_doc({"doctype": "Coworker Message", "conversation": conv_name, "seq": next_seq(conv_name),
                          "role": role, "content": content or "", **kw})
    doc.insert(ignore_permissions=True)
    frappe.db.set_value("Coworker Conversation", conv_name, "last_message_at", now_datetime(), update_modified=True)
    return doc


def resolve_provider(coworker, settings, override=None):
    name = override or coworker.provider or settings.default_provider
    if not name:
        name = frappe.db.get_value("Coworker Provider", {"is_default": 1, "enabled": 1}, "name")
    if not name:
        raise TurnError(_("No AI provider is set up yet. An administrator can add one in the Coworker setup wizard."))
    doc = frappe.get_doc("Coworker Provider", name)
    if not doc.enabled:
        raise TurnError(_("The AI provider {0} is disabled.").format(name))
    if settings.residency_mode == "Strict" and doc.data_location == "External":
        raise TurnError(_("Residency mode is Strict and {0} is an external provider. Use an in-Kingdom or "
                          "on-premises provider.").format(name))
    return doc


def fallback_provider(primary, settings):
    """The fallback must be enabled and keep data at least as close as the provider it replaces."""
    from neotec_coworker.automation.common import fallback_allowed

    name = settings.get("fallback_provider")
    if not name or name == primary.name or not frappe.db.exists("Coworker Provider", name):
        return None
    fb = frappe.get_doc("Coworker Provider", name)
    if not fb.enabled or not fallback_allowed(primary.data_location, fb.data_location, settings.residency_mode):
        return None
    if fb.get("tool_test_status") == "Failed":
        return None
    return fb


def _chat(state, settings, ctx, system, messages, tool_specs, temperature):
    try:
        return llm.chat(state["cfg"], system, messages, tool_specs, temperature=temperature)
    except llm.ProviderError:
        if state["fell_back"]:
            raise
        fb = fallback_provider(state["provider"], settings)
        if not fb:
            raise
        frappe.log_error(title=f"Neotec Coworker: provider {state['provider'].name} failed, using {fb.name}")
        state.update(cfg=llm.config_from_doc(fb), provider=fb, fell_back=True)
        ctx["provider"] = fb.name
        if ctx.get("run"):
            from neotec_coworker.automation import playbooks

            playbooks.set_provider(ctx["run"], fb.name)
        return llm.chat(state["cfg"], system, messages, tool_specs, temperature=temperature)


def tokens_used_today(user) -> int:
    val = frappe.db.sql("""select ifnull(sum(m.tokens_in + m.tokens_out), 0)
        from `tabCoworker Message` m join `tabCoworker Conversation` c on c.name = m.conversation
        where c.user = %s and m.creation >= %s""", (user, nowdate()))
    return cint(val[0][0])


def granted_tools(coworker) -> tuple[dict, list[dict]]:
    grants = {g.tool: (g.mode or "Default") for g in coworker.tools if (g.mode or "Default") != "Off"}
    disabled = set(frappe.get_all("Coworker Tool", filters={"enabled": 0}, pluck="name"))
    specs = []
    for name in grants:
        if name in disabled:
            continue
        spec = registry.get_tool(name)
        if spec:
            specs.append({"name": spec["name"], "description": spec["description"], "schema": spec["schema"]})
    return grants, specs


def can_use(coworker, user=None) -> bool:
    roles = set(frappe.get_roles(user or frappe.session.user))
    if roles & {"System Manager", "Coworker Admin"}:
        return True
    if "Coworker User" not in roles:
        return False
    allowed = {r.role for r in coworker.allowed_roles or []}
    return not allowed or bool(allowed & roles)


def shape_tool_result(out: dict, limit: int) -> tuple[str, dict | None, str]:
    """Returns (content for the model, ui blocks or None, message status)."""
    status = {"ok": "ok", "pending": "pending", "refused": "refused"}.get(out.get("status"), "error")
    blocks = None
    payload = {k: v for k, v in out.items() if k != "log"}
    result = out.get("result")
    if isinstance(result, dict) and "__blocks__" in result:
        blocks = result["__blocks__"]
        payload["result"] = {"shown_to_user": True, "problems": result.get("problems") or []}
    return redact.to_json(payload, limit), blocks, status


# ---------------------------------------------------------------- entry points

def enqueue_turn(conversation: str, resume: bool = False):
    frappe.db.set_value("Coworker Conversation", conversation, {"status": "Running", "last_error": None},
                        update_modified=False)
    kwargs = dict(queue="long", timeout=1500, conversation=conversation, enqueue_after_commit=True)
    try:
        frappe.enqueue("neotec_coworker.engine.runner.run_turn", job_id=f"ntc::{conversation}",
                       deduplicate=True, **kwargs)
    except TypeError:  # older signature without dedupe
        frappe.enqueue("neotec_coworker.engine.runner.run_turn", **kwargs)


def run_turn(conversation: str):
    conv = frappe.get_doc("Coworker Conversation", conversation)
    frappe.set_user(conv.user)
    try:
        _run_turn(conv)
    finally:
        if conv.get("run"):
            from neotec_coworker.automation import playbooks

            playbooks.after_resumed_turn(conv.name)


def _run_turn(conv):
    conversation = conv.name
    try:
        _loop(conv)
    except TurnError as e:
        _fail(conv, str(e))
    except llm.ProviderError as e:
        _fail(conv, _("The AI provider returned an error: {0}").format(str(e)[:400]))
    except Exception as e:  # noqa: BLE001
        frappe.db.rollback()
        frappe.log_error(title="Neotec Coworker turn failed", reference_doctype="Coworker Conversation",
                         reference_name=conversation)
        _fail(conv, _("Something went wrong while working on this. The administrator can see the details in "
                      "the Error Log. ({0})").format(e.__class__.__name__))


def _fail(conv, message):
    add_message(conv.name, "assistant", message, status="error")
    frappe.db.set_value("Coworker Conversation", conv.name, {"status": "Idle", "last_error": message[:500]})
    frappe.db.commit()
    publish(conv.name, conv.user, "Idle")


def _loop(conv):
    settings = gateway.settings()
    if not settings.enabled:
        raise TurnError(_("Neotec Coworker is switched off by the administrator."))
    coworker = frappe.get_doc("AI Coworker", conv.coworker)
    if not coworker.enabled:
        raise TurnError(_("The coworker {0} is disabled.").format(coworker.name))
    if conv.channel != "Routine" and not can_use(coworker, conv.user):
        raise TurnError(_("You do not have access to the coworker {0}.").format(coworker.name))

    from neotec_coworker.automation import playbooks

    rctx = playbooks.run_context(conv)
    provider = resolve_provider(coworker, settings, rctx.provider if rctx else None)
    if rctx and provider.get("tool_test_status") == "Failed":
        raise TurnError(_("The model on provider {0} failed the tool-calling self-test, so it cannot run playbooks. "
                          "Choose another model or provider, or test again.").format(provider.name))
    limit = cint(settings.daily_token_limit)
    if limit and not rctx and tokens_used_today(conv.user) >= limit:
        raise TurnError(_("Your daily AI allowance is used up. It resets tomorrow."))

    cfg = llm.config_from_doc(provider)
    grants, tool_specs = granted_tools(coworker)
    if rctx:
        grants, tool_specs = playbooks.adjust_tools(rctx, grants, tool_specs)
        playbooks.set_provider(rctx.name, provider.name)
    location = provider.data_location
    mask_personal = location == "External" and cint(settings.redact_external)
    sensitive = gateway.sensitive_doctypes()
    ctx = {"user": conv.user, "coworker": coworker.name, "conversation": conv.name,
           "initiator": CHANNEL_INITIATOR.get(conv.channel, "Chat"), "provider": provider.name,
           "provider_location": location, "grants": grants, "roles": set(frappe.get_roles(conv.user)),
           "run": rctx.name if rctx else None, "read_only": bool(rctx and rctx.read_only),
           "dry_run": bool(rctx and rctx.dry_run)}
    frappe.flags.ntc_external = location == "External"
    frappe.flags.ntc_coworker = coworker.name
    frappe.flags.ntc_run = rctx.name if rctx else None

    max_steps = (rctx and rctx.max_steps) or cint(coworker.max_steps) or cint(settings.max_steps) or 8
    token_cap = rctx.max_tokens if rctx else 0
    state = {"cfg": cfg, "provider": provider, "fell_back": False}
    max_calls = (rctx and rctx.max_tool_calls) or cint(settings.max_tool_calls) or 12
    window = cint(settings.history_window) or 30
    char_limit = cint(settings.tool_result_char_limit) or 12000
    temperature = coworker.temperature if coworker.temperature not in (None, 0) else None
    calls_used = 0
    finished = False

    for _step in range(max_steps):
        if frappe.db.get_value("Coworker Conversation", conv.name, "status") == "Stopping":
            add_message(conv.name, "assistant", _("Stopped."), status="ok")
            finished = True
            break
        conv.reload()
        if token_cap and cint(conv.total_tokens) >= token_cap:
            playbooks.mark_budget(rctx.name)
            add_message(conv.name, "assistant", _("The token limit for this run was reached before it finished."),
                        status="error")
            finished = True
            break
        system = context.system_prompt(conv, coworker, settings, location, sensitive)
        messages = context.history(conv, window, mask_personal)
        result = _chat(state, settings, ctx, system, messages, tool_specs, temperature)

        add_message(conv.name, "assistant", result.text,
                    tool_calls=json.dumps(result.tool_calls, ensure_ascii=False) if result.tool_calls else None,
                    tokens_in=result.tokens_in, tokens_out=result.tokens_out, status="ok")
        frappe.db.sql("update `tabCoworker Conversation` set total_tokens = ifnull(total_tokens,0) + %s where name=%s",
                      (result.tokens_in + result.tokens_out, conv.name))
        frappe.db.commit()
        publish(conv.name, conv.user, "Running")

        if not result.tool_calls:
            finished = True
            break

        pending = False
        for call in result.tool_calls:
            tmsg = add_message(conv.name, "tool", "", tool_name=call["name"], tool_call_id=call["id"])
            frappe.db.commit()
            if calls_used >= max_calls:
                out = {"status": "refused", "message": "Tool-call limit for this turn reached. Summarise what you have."}
            else:
                ctx["message"] = tmsg.name
                out = gateway.execute(ctx, call["name"], call.get("arguments") or {})
                calls_used += 1
            content, blocks, status = shape_tool_result(out, char_limit)
            frappe.db.set_value("Coworker Message", tmsg.name, {
                "content": content, "status": status, "approval": out.get("approval"),
                "blocks": json.dumps(blocks, ensure_ascii=False) if blocks else None}, update_modified=False)
            frappe.db.commit()
            publish(conv.name, conv.user, "Running")
            pending = pending or status == "pending"

        if pending:
            frappe.db.set_value("Coworker Conversation", conv.name, "status", "Waiting Approval")
            frappe.db.commit()
            publish(conv.name, conv.user, "Waiting Approval")
            return

    if not finished:
        if rctx:
            add_message(conv.name, "assistant", _("The step limit for this run was reached before it finished. "
                                                  "Raise Max steps on the playbook if this keeps happening."),
                        status="error")
        else:
            add_message(conv.name, "assistant",
                        _("I reached the step limit for one turn. Reply 'continue' and I will carry on."), status="ok")
    frappe.db.set_value("Coworker Conversation", conv.name, "status", "Idle")
    frappe.db.commit()
    publish(conv.name, conv.user, "Idle")
    if not rctx:
        _maybe_summarize(conv.name, state["cfg"], window)


def _maybe_summarize(conv_name, cfg, window):
    """Keeps long conversations coherent: folds messages that dropped out of the window into a summary."""
    try:
        conv = frappe.get_doc("Coworker Conversation", conv_name)
        last = next_seq(conv_name) - 1
        boundary = last - window
        if boundary - cint(conv.summary_upto) < 20:
            return
        rows = frappe.get_all("Coworker Message",
                              filters={"conversation": conv_name, "seq": ["between", [cint(conv.summary_upto) + 1, boundary]],
                                       "role": ["in", ["user", "assistant"]]},
                              fields=["role", "content"], order_by="seq asc")
        transcript = "\n".join(f"{r.role}: {(r.content or '')[:600]}" for r in rows if r.content)
        if not transcript:
            return
        prompt = ("Summarise this part of a business conversation in at most 12 bullet points. Keep figures, "
                  "document names, decisions and open questions. Same language as the conversation.")
        prior = f"Earlier summary:\n{conv.summary}\n\n" if conv.summary else ""
        res = llm.chat(cfg, prompt, [{"role": "user", "content": prior + transcript[:24000]}], [])
        frappe.db.set_value("Coworker Conversation", conv_name,
                            {"summary": res.text[:6000], "summary_upto": boundary}, update_modified=False)
        frappe.db.commit()
    except Exception:  # noqa: BLE001 - summaries are best effort
        frappe.db.rollback()


def run_once(conversation: str) -> str:
    """Synchronous variant for routines: runs the turn in the current job and returns the last answer."""
    frappe.db.set_value("Coworker Conversation", conversation, "status", "Running")
    run_turn(conversation)
    row = frappe.get_all("Coworker Message", filters={"conversation": conversation, "role": "assistant"},
                         fields=["content", "status"], order_by="seq desc", limit_page_length=1)
    if row and row[0].status == "error":
        raise TurnError(row[0].content)
    return row[0].content if row else ""
