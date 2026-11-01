# Copyright (c) 2026, Neotec Integrated Solutions
# License: Proprietary
"""1.1.0: give existing coworkers the new automation tools once.

Seeders never touch an administrator's coworkers, so new grants for sites upgraded from 1.0 come from this patch:
  * General Assistant: list, run and read playbooks from chat.
  * MCP Gateway: external AI clients can list and read playbooks; starting one needs a person's approval (Ask).
"""

import frappe

GRANTS = {
    "General Assistant": {"list_playbooks": "Default", "run_playbook": "Default", "get_run": "Default"},
    "MCP Gateway": {"list_playbooks": "Default", "run_playbook": "Ask", "get_run": "Default"},
}


def execute():
    from neotec_coworker.setup.seed import sync_tool_registry

    if not frappe.db.table_exists("Coworker Tool"):
        return
    sync_tool_registry()
    for coworker, tools in GRANTS.items():
        if not frappe.db.exists("AI Coworker", coworker):
            continue
        doc = frappe.get_doc("AI Coworker", coworker)
        have = {g.tool for g in doc.tools}
        added = False
        for tool, mode in tools.items():
            if tool not in have and frappe.db.exists("Coworker Tool", tool):
                doc.append("tools", {"tool": tool, "mode": mode})
                added = True
        if added:
            doc.flags.ignore_permissions = True
            doc.save()
    frappe.db.commit()
