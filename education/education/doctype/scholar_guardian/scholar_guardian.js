// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholar Guardian', {
  id_number(frm, cdt, cdn) {
    const row = locals[cdt][cdn]
    const idNumber = (row.id_number || '').trim()
    if (!idNumber) {
      return
    }

    const duplicate = (frm.doc.guardians || []).find(
      (guardian) =>
        guardian.name !== row.name &&
        (guardian.id_number || '').trim().toLowerCase() ===
          idNumber.toLowerCase()
    )
    if (!duplicate) {
      return
    }

    frappe.model.set_value(cdt, cdn, 'id_number', '')
    frappe.msgprint({
      title: __('Duplicate Guardian'),
      indicator: 'red',
      message: __(
        'ID Number {0} is already used for a guardian in row {1}. Enter each guardian only once.',
        [idNumber, duplicate.idx]
      ),
    })
  },
})
