// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fee Request Payment', {
  onload(frm) {
    frm.ignore_doctypes_on_cancel_all = ['Fee Request']
  },
  refresh(frm) {
    frm.trigger('set_filters')
  },
  scholar(frm) {
    if (frm.doc.scholar) {
      frm.trigger('set_filters')
    }
  },
  academic_year(frm) {
    if (frm.doc.academic_year) {
      frm.trigger('set_filters')
      frm.set_value('academic_term', '')
      frm.set_query('academic_term', function () {
        return {
          filters: {
            academic_year: frm.doc.academic_year,
          },
        }
      })
    }
  },

  set_filters(frm) {
    frm.set_query('fee_request', function () {
      return {
        filters: {
          scholar: frm.doc.scholar,
          docstatus: 1,
          payment_status: ['in', ['Unpaid', 'Partially Paid']],
          academic_year: frm.doc.academic_year,
          academic_term: frm.doc.academic_term,
        },
      }
    })
  },
})
