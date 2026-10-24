// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fee Request Payment', {
  onload(frm) {
    frm.ignore_doctypes_on_cancel_all = ['Fee Request']
  },
  refresh(frm) {
    frm.trigger('set_filters')
    frm.trigger('load_terms')
    frm.trigger('load_target_terms')
  },
  scholar(frm) {
    if (frm.doc.scholar) {
      frm.trigger('set_filters')
    }
  },
  academic_year(frm) {
    if (frm.doc.academic_year) {
      frm.trigger('set_filters')
    }
  },
  fee_request(frm) {
    frm.set_value('academic_term', '')
    frm.trigger('load_terms')
  },
  target_fee_request(frm) {
    frm.set_value('target_academic_term', '')
    frm.trigger('load_target_terms')
  },

  load_terms(frm) {
    load_fee_request_terms(frm, 'fee_request', 'academic_term')
  },

  load_target_terms(frm) {
    load_fee_request_terms(frm, 'target_fee_request', 'target_academic_term')
  },

  set_filters(frm) {
    const fee_request_filters = {
      scholar: frm.doc.scholar,
      docstatus: 1,
      academic_year: frm.doc.academic_year,
    }
    frm.set_query('fee_request', () => ({ filters: fee_request_filters }))
    frm.set_query('target_fee_request', () => ({
      filters: fee_request_filters,
    }))
  },
})

// Limit a term field to the terms on the selected Fee Request; pick it when there is only one.
function load_fee_request_terms(frm, fee_request_field, term_field) {
  const fee_request = frm.doc[fee_request_field]
  if (!fee_request) {
    return
  }

  frappe.call({
    method:
      'education.education.doctype.fee_request.fee_request.get_fee_request_terms',
    args: { fee_request },
    callback: (r) => {
      const terms = (r.message || []).map((row) => row.academic_term)
      frm.set_query(term_field, () => ({
        filters: { name: ['in', terms] },
      }))
      if (
        terms.length === 1 &&
        !frm.doc[term_field] &&
        frm.doc.docstatus === 0
      ) {
        frm.set_value(term_field, terms[0])
      }
    },
  })
}
