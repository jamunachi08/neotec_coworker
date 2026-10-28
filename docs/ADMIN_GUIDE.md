# Neotec Coworker — Administrator Guide

## How a request flows

1. A user writes in the chat (or a routine fires, or an MCP client calls).
2. A background job builds the context: the coworker's role and instructions, company instructions,
   the user's roles, remembered facts, the document the chat was opened from, and the recent messages.
3. The model answers or asks for tools.
4. Each tool call passes the **gateway**:

   | Check | Outcome when it fails |
   |---|---|
   | Coworker is granted the tool (and the tool is enabled) | Refused |
   | Residency: sensitive DocType with an external provider in Guarded mode | Refused |
   | Policy rules (Deny → Require Approval → Allow) | Refused or waits for approval |
   | Grant mode (Default / Auto / Ask) | Waits for approval |
   | Audit row written and committed | Nothing runs |

5. The tool runs **as the user**, with ERPNext permissions, inside a savepoint (rolled back on error).
6. The result is recorded and returned to the model; the loop continues until it answers.

## Grant modes

| Mode | Reading tools | Tools that change data |
|---|---|---|
| Default | Run | Ask the user first |
| Auto | Run | Run (policies still apply) |
| Ask | Ask first | Ask first |
| Off | Not available | Not available |

## Policy rules

Fields: Effect, Tool Pattern (glob; comma-separated allowed), Only for DocType, Only for Coworker,
Only when started by (Chat, Form, Routine, MCP), Only for users with Role, Condition, Approver Role.

Deny beats Require Approval, which beats Allow. A condition that raises an error counts as matched for
Deny and Require Approval rules, so a broken rule refuses rather than opens.

Names available in a condition: `tool`, `args`, `doctype`, `is_write`, `risk`, `user`, `roles`,
`coworker`, `initiator`, `flt`, `cint`, `getdate`, `nowdate`.

Examples:

```python
# Rule "Sales orders need a Sales Manager": effect Require Approval, approver Sales Manager
doctype == "Sales Order"
# Rule that applies only on Saudi working days (Sunday to Thursday)
getdate(nowdate()).weekday() in (6, 0, 1, 2, 3)
# Keep one coworker away from item masters
coworker == "Sales Assistant" and doctype == "Item"
```

### Starter KSA policy pack

| Rule | Effect |
|---|---|
| Never submit documents | Deny `submit_document` |
| Routines cannot change data | Deny writes (except notifications) when started by Routine |
| No changes to sensitive HR records | Deny drafts on Employee, Salary Slip, Payroll… |
| External e-mail needs an approver | Require approval by Coworker Approver |
| Payments and journals need finance approval | Require approval by Accounts Manager |
| MCP clients ask before any change | Require approval for writes from MCP |
| Notifications run without asking | Allow `notify_user` |

## Data residency (PDPL)

* **Provider data location**: External, In Kingdom (KSA) or On-Premises, set per provider.
* **Residency mode** (Coworker Settings):
  * *Guarded* (default): DocTypes listed under *Sensitive DocTypes* are never read for an External
    provider, and document context from them is withheld.
  * *Strict*: External providers cannot be used at all.
  * *Open*: no residency checks.
* **Masking**: with an External provider, national ID / Iqama numbers, Saudi IBANs, card numbers
  (Luhn-checked), Saudi mobile numbers and e-mail addresses are masked in everything sent to the model.
  Secrets are always masked in the audit trail.

## Audit trail

`Coworker Action Log` is append-only: written by the gateway, never editable or deletable from the UI.
Retention is set in days (0 keeps everything, recommended for NCA ECC evidence). Approvals are kept too.

## Coworkers

Edit under **AI Coworker**: job title (EN/AR), description, instructions, starter prompts, provider
override, temperature, granted tools, allowed roles, knowledge and memory switches, max steps.
**Grant all read-only tools** adds every built-in reading tool in one click.

## Built-in tools

| Category | Tools |
|---|---|
| Data | describe_doctype, search_documents, get_document, count_documents, aggregate, list_reports, run_report, global_search, current_user |
| Finance | receivables_aging, payables_due, sales_summary, sales_by_item, cash_position |
| Stock | stock_levels, low_stock |
| KSA Compliance | ksa_vat, ksa_validate_vat_number, ksa_validate_iban, ksa_end_of_service, ksa_invoice_check |
| Knowledge / Memory | search_knowledge, remember_fact |
| Interface | render_ui |
| Actions (change data) | create_draft_document, update_draft_document, add_comment, create_todo, notify_user, send_email, submit_document |
| Actions (read) | approval_status |

## Knowledge base

Add a **Coworker Knowledge** record per policy or manual: paste text, or attach .txt, .md, .csv or .pdf.
Text is split into passages and indexed with Arabic normalisation (diacritics, alef/ya/ta-marbuta forms,
the definite article, Arabic-Indic digits). Limit a document to one coworker with *Only for Coworker*.

## Routines

Fields: coworker, run as, frequency (15 minutes floor, hourly, daily, weekly, monthly, cron), instruction,
delivery (bell, e-mail, chat webhook). A user may only create routines that run as themselves. After the
configured number of consecutive failures the routine switches itself off and tells its owner.

## MCP

**ERPNext as an MCP server.** Enable it in Coworker Settings and choose the coworker whose grants define
the exposed tools (default: *MCP Gateway*). Clients connect over Streamable HTTP:

```json
{
  "mcpServers": {
    "erpnext": {
      "type": "http",
      "url": "https://<site>/api/method/neotec_coworker.mcp.server.handle",
      "headers": { "Authorization": "token <api_key>:<api_secret>" }
    }
  }
}
```

Generate the key on the user's own User record (API Access). Calls run as that user, are treated as
coming from an external provider for residency purposes, and writes wait for approval in ERPNext.

**External MCP servers for coworkers.** Add a *Coworker MCP Server* (https URL and auth header), press
**Discover tools**, list the read-only tools, then grant `mcp_<name>__<tool>` on an AI Coworker.

## Extending from another app

```python
# hooks.py of your app
neotec_coworker_tools = ["my_app.coworker.get_tools"]
neotec_coworker_before_tool = ["my_app.coworker.before_tool"]   # raise to refuse
neotec_coworker_after_tool = ["my_app.coworker.after_tool"]

# my_app/coworker.py
def get_tools():
    return [{
        "name": "project_margin",
        "label": "Project margin",
        "description": "Margin of a project from its costing.",
        "parameters": {"project": {"type": "string"}, "__required__": ["project"]},
        "is_write": False, "risk": "Low",
        "fn": "my_app.coworker.project_margin",
    }]
```

Run `bench migrate` (or press nothing: tools sync on every migrate), then grant the tool on a coworker.

## Limits and costs

Coworker Settings: max steps per turn, max tool calls per turn, messages kept in context (older ones are
summarised automatically), tool result size, daily token allowance per user, approval expiry.
