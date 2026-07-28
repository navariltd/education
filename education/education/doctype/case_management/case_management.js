// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Case Management', {
  refresh(frm) {},
  scholar: (frm) => {
    if (frm.doc.scholar) {
      frappe.db.get_value('Scholar', frm.doc.scholar, 'status').then((r) => {
        console.log(r.message)
        frm.set_value('scholarship_status', r.message.status) // Open
      })
    }
  },
})
