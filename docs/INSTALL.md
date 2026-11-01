# Installing Neotec Coworker

## 1. Frappe Cloud (recommended)

1. Push this repository to GitHub (private is fine), e.g. `jamunachi08/neotec_coworker`.
2. Frappe Cloud → **Bench Groups** → your group → **Apps** → **Add App** → **GitHub** → choose the
   repository and branch. Frappe Cloud reads `pyproject.toml`; there are no extra Python packages.
3. **Deploy** the bench group.
4. **Sites** → your site → **Apps** → **Install App** → Neotec Coworker. Installing creates the roles,
   registers the tools, loads the KSA policy pack and the starter coworkers, and gives every System
   Manager the Coworker Admin, User and Approver roles.
5. Open `https://<your-site>/app/coworker-setup` and follow the four steps.

Later updates: push to the branch and redeploy; `after_migrate` re-syncs tools and adds any missing
starter records without touching your edits.

## 2. Self-hosted bench

```sh
bench get-app https://github.com/<you>/neotec_coworker
bench --site <site> install-app neotec_coworker
bench --site <site> migrate
bench build --app neotec_coworker
bench restart
```

The scheduler and the `long` queue workers must be running:

```sh
bench --site <site> enable-scheduler
```

## 3. Setup wizard (`/app/coworker-setup`)

**Step 1, provider.** Pick a preset, paste the API key, confirm the model id and press
**Save and test connection**. The result is shown immediately.

| Preset | Base URL | Notes |
|---|---|---|
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | Key from Google AI Studio |
| OpenAI | `https://api.openai.com/v1` | Enter the model id you are licensed for |
| Anthropic Claude | `https://api.anthropic.com` | e.g. `claude-sonnet-5-5` |
| Azure OpenAI | `https://NAME.openai.azure.com/openai/deployments/DEPLOYMENT` | Model = deployment name |
| On-premises (Ollama / vLLM) | `http://server:11434/v1` | Model must support tool calling |
| NeotecAI On-Premises | `https://host/v1` | Data location: On-Premises |

Choose **Data location** honestly: it drives the residency guard.

**Step 2, coworkers.** Tick the coworkers your users should see.

**Step 3, governance and access.** Residency mode, masking, self-approval, MCP endpoint, and who gets
the Coworker User role (you, or every active System User).

**Step 4, health check.** Every line should be green: provider answered, scheduler and workers running,
tools registered, policies active, users with access.

## 4. Roles

| Role | Can |
|---|---|
| Coworker User | Chat with the coworkers they are allowed to use; manage own routines and memory |
| Coworker Approver | Approve or reject actions coworkers request |
| Coworker Admin | Configure providers, coworkers, policies, knowledge; read the audit trail |

Policy rules can name any ERPNext role as approver, e.g. Accounts Manager for draft payments.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| Message sent, nothing happens | Workers not running, or the `long` queue is stopped. Check the health step. |
| "No AI provider is set up yet" | Finish step 1 of the wizard. |
| Provider returned HTTP 400 about tools | The chosen model does not support tool calling. Pick another model. |
| Conversation stuck on "Working" | Press **Unstick** in the chat header (appears after 20 minutes). |
| Routine never runs | Scheduler disabled. Enable it. |
| "refused by policy" | Open **Activity** in the chat to see the rule; adjust it under Coworker Policy Rule. |
| Playbook run stays Queued | The `long` queue has no worker. Check the health step. |
| Trigger never fires | Is it enabled, does **Test on a document** match, and is the cooldown over? Changes made by coworkers never fire triggers. |
| Automated playbook refuses to create a draft | Intended: rule *Routines cannot change data*. Run it by hand, or narrow that rule. |
| Anything else in automation | Open /app/coworker-health and press **Run checks now**; each issue says how to fix it. |

## 6. Upgrading from 1.0

Push and deploy as usual. The migration adds the automation DocTypes, loads the starter packs, and the patch
`v1_1.grant_automation_tools` adds list_playbooks, run_playbook and get_run to General Assistant and MCP
Gateway. Existing routines keep working unchanged (Runs = Prompt). Then, in Coworker Settings, fill in
*Company priorities* and choose a *Fallback AI provider* and a *health channel*.
