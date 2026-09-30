// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

const PRIMARY_GUARDIAN_METHOD =
  'education.education.doctype.scholar_guardian.scholar_guardian.get_primary_guardian'

frappe.ui.form.on('Case Management', {
  refresh(frm) {},
  scholar: (frm) => {
    if (frm.doc.scholar) {
      frappe.db.get_value('Scholar', frm.doc.scholar, 'status').then((r) => {
        frm.set_value('scholarship_status', r.message.status)
      })
      frm.trigger('set_primary_guardian')
      return
    }

    frm.set_value('scholarship_status', '')
    frm.trigger('set_primary_guardian')
  },

  set_primary_guardian(frm) {
    if (!frm.doc.scholar) {
      frm.set_value('primary_guardian_name', '')
      frm.set_value('primary_guardian_contact', '')
      frm.set_value('relationship_to_student', '')
      return
    }

    frappe
      .xcall(PRIMARY_GUARDIAN_METHOD, { scholar: frm.doc.scholar })
      .then((guardian) => {
        guardian = guardian || {}
        frm.set_value('primary_guardian_name', guardian.guardian_name || '')
        frm.set_value(
          'primary_guardian_contact',
          guardian.guardian_contact || ''
        )
        frm.set_value(
          'relationship_to_student',
          guardian.relationship_to_student || ''
        )
      })
  },
})
