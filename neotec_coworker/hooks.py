app_name = "neotec_coworker"
app_title = "Neotec Coworker"
app_publisher = "Neotec Integrated Solutions"
app_description = "Governed AI coworkers for ERPNext: policy-checked tools, approvals, audit trail, routines, knowledge and an MCP endpoint."
app_email = "support@neotec.ai"
app_license = "Proprietary"
app_logo_url = "/assets/neotec_coworker/images/logo.svg"

add_to_apps_screen = [
    {
        "name": "neotec_coworker",
        "logo": "/assets/neotec_coworker/images/logo.svg",
        "title": "Neotec Coworker",
        "route": "/app/coworker",
    }
]

app_include_js = ["/assets/neotec_coworker/js/coworker_launcher.js"]
app_include_css = ["/assets/neotec_coworker/css/coworker.css"]

before_install = "neotec_coworker.install.before_install"
after_install = "neotec_coworker.install.after_install"
after_migrate = "neotec_coworker.install.after_migrate"

boot_session = "neotec_coworker.boot.boot_session"

scheduler_events = {
    "cron": {
        "*/5 * * * *": ["neotec_coworker.routines.tick"],
    },
    "daily": [
        "neotec_coworker.engine.gateway.expire_approvals",
        "neotec_coworker.engine.gateway.purge_old_logs",
        "neotec_coworker.automation.health.daily",
    ],
}

# Triggers: one cached lookup per save; only DocTypes with an enabled Coworker Trigger go further.
doc_events = {
    "*": {
        "after_insert": "neotec_coworker.automation.triggers.on_event",
        "on_update": "neotec_coworker.automation.triggers.on_event",
        "on_submit": "neotec_coworker.automation.triggers.on_event",
        "on_cancel": "neotec_coworker.automation.triggers.on_event",
    }
}

# Extension points for other apps (see docs/ADMIN_GUIDE.md):
#   neotec_coworker_tools = ["my_app.coworker.get_tools"]            -> list of tool dicts
#   neotec_coworker_before_tool = ["my_app.coworker.before_tool"]    -> raise to refuse
#   neotec_coworker_after_tool = ["my_app.coworker.after_tool"]
