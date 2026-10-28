// Copyright (c) 2026, Neotec Integrated Solutions
frappe.ui.form.on("Coworker Provider", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Test connection"), () => {
			frm.call({ method: "test_connection", doc: frm.doc, freeze: true, freeze_message: __("Calling the provider…") })
				.then((r) => {
					const res = r.message || {};
					frappe.show_alert({ message: res.message, indicator: res.ok ? "green" : "red" }, 10);
					frm.reload_doc();
				});
		});
	},
});
