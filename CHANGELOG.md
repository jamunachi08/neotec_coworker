# Changelog

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
