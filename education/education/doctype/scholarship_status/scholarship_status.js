// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholarship Status', {
  refresh(frm) {
    frm.set_query('parent_scholar_status', function () {
      return {
        filters: {
          is_group: 1,
          name: ['!=', frm.doc.name],
        },
      }
    })
  },
})
