// Copyright (c) 2026, Navari Limited and contributors
// For license information, please see license.txt

function set_class_progression_queries(frm) {
  let eligible_classes = (frm.doc.eligible_classes || []).map(
    (row) => row.class
  )

  ;['current_class', 'next_class'].forEach((field) => {
    frm.set_query(field, 'class_progression', () => ({
      filters: {
        name: ['in', eligible_classes],
      },
    }))
  })

  frm.refresh_fields('class_progression')
}

frappe.ui.form.on('Scholarship Promotion Rule', {
  onload(frm) {
    if (frm.is_new()) {
      for (table of [
        'status_progression',
        'eligible_classes',
        'class_progression',
      ]) {
        frm.clear_table(table)
      }
    }
  },
  refresh(frm) {
    set_class_progression_queries(frm)
  },
  eligible_classes_add(frm) {
    set_class_progression_queries(frm)
  },
  eligible_classes_remove(frm) {
    set_class_progression_queries(frm)
  },
})

frappe.ui.form.on('Eligible Class', {
  class(frm) {
    set_class_progression_queries(frm)
  },
})

frappe.ui.form.on('Class Progression', {
  is_final: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn)
    if (row.is_final) {
      frappe.model.set_value(cdt, cdn, 'next_class', '')
    }
  },
})
