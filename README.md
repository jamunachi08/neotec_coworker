# Neotec Coworker

Governed AI coworkers inside ERPNext. Each coworker has a job, a set of granted tools and the same
permissions as the person it works for. Every action is checked against company policy and recorded
before it runs. Built for Saudi Arabia: Arabic and English, data-residency controls for PDPL, and
calculators for VAT, end-of-service and e-invoicing checks.

Runs entirely inside a Frappe site, so it installs on Frappe Cloud with no extra servers.

| | |
|---|---|
| Version | 1.0.0 |
| Frappe / ERPNext | v15 and v16 |
| Publisher | Neotec Integrated Solutions |
| Licence | Proprietary (see license.txt) |

## What a user gets

- A chat page at `/app/coworker` with seven ready coworkers: General Assistant, Finance Analyst,
  Sales Assistant, Procurement Checker, HR & Labor Law Advisor, Inventory Watch and Knowledge Desk.
- Answers with KPI tiles, tables, charts, clickable document lists, small forms and quick-action buttons.
- **Ask Coworker** on every ERPNext form: the conversation starts already knowing that document.
- Approval cards in the chat: a coworker that wants to change data waits for **Approve and run**.
- Routines: "every Sunday at 7:00, send me receivables over 90 days" delivered to the bell, e-mail or a
  Teams / Slack / Google Chat channel.

## What an administrator controls

- **Providers**: Google Gemini, OpenAI, Anthropic Claude, Azure OpenAI, on-premises Ollama / vLLM or
  NeotecAI. Each provider records where data is processed.
- **Residency**: Guarded mode keeps sensitive DocTypes (employees, salaries, bank accounts) away from
  external providers; Strict mode blocks external providers entirely. Personal data is masked before it
  leaves for an external provider.
- **Policies**: deny-first rules by tool, DocType, coworker, role, channel or a Python condition.
  A rule can require approval by a role; the requester can never approve their own request then.
- **Audit trail**: every tool call, permitted or refused, with rule, masked arguments, result and duration.
- **MCP**: expose ERPNext to external AI clients through the same rules, or plug external MCP tools into coworkers.

## Install

See [docs/INSTALL.md](docs/INSTALL.md). In short, on Frappe Cloud: add the app from GitHub to your
bench group, deploy, install on the site, then open **/app/coworker-setup**.

## Documentation

- [Installation](docs/INSTALL.md)
- [Administrator guide](docs/ADMIN_GUIDE.md)
- [دليل البدء السريع](docs/QUICK_START_AR.md)

## Development checks

```sh
python verify_tree.py        # structure, links, hooks, naming, version
python -m pytest tests -q    # policy, masking, KSA calculators, blocks, provider adapters
```
