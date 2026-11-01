# Changelog

## 1.2.0 — 2026-11-08

Open models: run Qwen, gpt-oss, Gemma, Llama, Mistral and other open-weight models on your own GPU server.

- **Open models guide**: a catalogue of open-weight models with licence, GPU size, Arabic quality and what each
  is suitable for (coworkers, light use, data centre). Open it from any provider or the setup wizard.
- **Find models on this server**: lists the models installed on an Ollama, vLLM or other OpenAI-compatible
  server, labels the ones the catalogue knows, and fills in the model id with one click.
- **Tool-calling self-test** on every provider: four checks (right tool and argument, answers from the result,
  Arabic request, no tool when none is needed). Passed, Partial or Failed. Playbooks refuse a provider that
  failed, a failed provider is never used as fallback, and changing the model resets the result.
- **New presets**: Ollama (self-hosted), vLLM (self-hosted), and a hosted router for open models, whose free
  models are labelled and always treated as External.
- **Health checks**: providers in use that failed or never ran the self-test; providers on a free hosted tier.
- **GPU server kit** (`deploy/gpu-server/`): Docker Compose with an Ollama or vLLM profile behind Caddy with
  TLS and an API key, a check script and a setup guide.
- docs/OPEN_MODELS.md (English and Arabic).


## 1.1.0 — 2026-11-01

Automation: coworkers now do recurring work on their own, safely, and report only what is new.

- **Playbooks** (Coworker Playbook): reusable tasks with a parameter, a mode (Read Only removes every write
  tool; Draft Changes stays under policy and approvals), optional provider override, and per-playbook limits
  for steps, tool calls and tokens. Run now from the form, with a dry run that changes nothing.
- **Output contract**: every result starts with a severity (info, success, warn, critical) or is exactly
  NOTHING_TO_REPORT, in which case the run stays silent. The coworker sees its previous result and says what
  changed.
- **No repeated findings**: playbooks record what they reported (Coworker Signal) and skip it for a
  configurable number of days.
- **Run history** (Coworker Run): status, severity, output, duration, tokens, estimated cost, tool calls,
  refused calls, delivery and quality score, linked to the full conversation.
- **Chains** (Coworker Chain): playbooks in sequence, each step its own background job (no worker time-outs);
  later steps read earlier results. Stop or continue on error.
- **Triggers** (Coworker Trigger): start a playbook after insert, on update, on submit or on cancel, with a
  Python condition, a parameter template and a cooldown per document. Changes made by coworkers never fire
  triggers; a trigger error never blocks the user's save. Test on a document from the form.
- **Channels** (Coworker Channel): bell, e-mail, Slack, Microsoft Teams (Adaptive Card), Google Chat,
  Telegram or a generic webhook, each with a minimum severity and a Send test button.
- **Routines** can now run a prompt, a playbook or a chain, and deliver to channels as well.
- **Company priorities and hard limits**, and a **voice** for reports, in Coworker Settings.
- **Fallback AI provider**, used only when it keeps data at least as close as the main one.
- **Monthly automation token budget**; issues at 80% and 100%.
- **Quality scoring** of results by a small model, under the same residency rule.
- **Health** (Coworker Issue, daily): issues for repeated failures, low quality, failing providers, budget
  and about 20 configuration checks (missing tool grants, disabled users or playbooks, triggers on DocTypes
  that no longer exist, unsafe fallback, failing channels). Issues close themselves when fixed; only changes
  are sent to the health channel. Old automated runs are purged after the retention period.
- **Coworker Health page** (/app/coworker-health): headline status, what needs attention, run history per
  playbook, cost and budget.
- **New tools**: list_playbooks, run_playbook, get_run (chat and MCP; over MCP, starting a run needs approval),
  signals_check, signals_record (granted to playbook runs automatically).
- **Starter packs**: Finance (Receivables Watch, Payables Due Soon, Cash Position Brief, Sales Pulse, Priority
  Brief), Operations (Overdue Sales Orders, Expiring Quotations, Low Stock Radar, Overdue Follow-ups, Purchase
  Invoice Match), KSA Compliance (E-Invoice Readiness Sweep, Supplier Master Hygiene, Employee Document
  Expiry); the Morning Finance Brief chain; a purchase-invoice trigger (disabled); a bell channel.
- Automated run conversations no longer crowd the chat list; open them from the run.
- Upgrade patch grants the new tools to General Assistant and MCP Gateway on existing sites.
- verify_tree.py now checks starter playbooks against coworker grants and patches against files.


## 1.0.0 — 2026-10-28

First release of Neotec Coworker.

- Coworkers: seven starter coworkers (General, Finance, Sales, Procurement, HR & Labor Law, Inventory,
  Knowledge) plus an MCP Gateway service coworker. Bilingual titles and starter prompts.
- Governance gateway: grant check, data-residency guard, deny-first policy rules, approvals with
  segregation of duties, append-only audit trail written before any action runs.
- Providers: OpenAI-compatible (Gemini, OpenAI, Groq, Ollama, vLLM, NeotecAI), Anthropic, Azure OpenAI.
- 32 built-in tools: generic data, finance, stock, KSA compliance (VAT, VAT number, IBAN,
  end-of-service, e-invoice readiness), knowledge, memory, visual answers and draft-only actions.
- Visual answers: KPI tiles, tables, charts, document lists, forms and quick actions.
- Knowledge base with Arabic-aware search and citations; personal memory.
- Routines with bell, e-mail and Teams / Slack / Google Chat delivery; auto-disable after failures.
- MCP server endpoint (ERPNext as governed tools) and MCP client (external tools for coworkers).
- Setup wizard, health check, "Ask Coworker" on every form, Ctrl+Shift+K shortcut.
