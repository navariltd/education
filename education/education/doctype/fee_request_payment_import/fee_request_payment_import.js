// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fee Request Payment Import', {
  onload(frm) {
    frm.ignore_doctypes_on_cancel_all = ['Fee Request', 'Fee Request Export']
  },
  refresh(frm) {
    if (frm.doc.payment_file && frm.doc.docstatus === 0) {
      frm.add_custom_button('Process File', () => {
        if (frm.is_dirty()) {
          frappe.throw('Please save the document before processing the file.')
        }
        frappe.call({
          method:
            'education.education.doctype.fee_request_payment_import.fee_request_payment_import.process_payment_file',
          args: {
            docname: frm.doc.name,
          },
          freeze: true,
          freeze_message: 'Processing payments...',
          callback: () => frm.reload_doc(),
        })
      })
    }
  },
  academic_year: function (frm) {
    frm.set_value('academic_term', '')
    frm.set_query('academic_term', () => {
      return {
        filters: {
          academic_year: frm.doc.academic_year,
        },
      }
    })
  },
})
