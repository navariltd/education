// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fee Request Payment', {
  onload(frm) {
    // An export or import covers many payments, so cancelling one payment must not
    // offer to cancel them. Its export lines go back to Pending on their own.
    frm.ignore_doctypes_on_cancel_all = [
      'Fee Request',
      'Fee Request Export',
      'Fee Request Payment Import',
    ]
    frm.fee_request_terms = {}
  },
  refresh(frm) {
    frm.trigger('set_filters')
    frm.trigger('load_target_terms')
  },
  scholar(frm) {
    if (frm.doc.scholar) {
      frm.trigger('set_filters')
    }
  },
  target_fee_request(frm) {
    frm.set_value('target_academic_term', '')
    frm.trigger('load_target_terms')
  },

  load_target_terms(frm) {
    const fee_request = frm.doc.target_fee_request
    if (!fee_request) {
      return
    }

    get_fee_request_terms(frm, fee_request).then((terms) => {
      const names = terms.map((row) => row.academic_term)
      frm.set_query('target_academic_term', () => ({
        filters: { name: ['in', names] },
      }))
      if (
        names.length === 1 &&
        !frm.doc.target_academic_term &&
        frm.doc.docstatus === 0
      ) {
        frm.set_value('target_academic_term', names[0])
      }
    })
  },

  set_filters(frm) {
    const fee_request_filters = {
      scholar: frm.doc.scholar,
      docstatus: 1,
    }
    frm.set_query('fee_request', 'allocations', () => ({
      filters: fee_request_filters,
    }))
    frm.set_query('academic_term', 'allocations', (doc, cdt, cdn) => {
      const row = locals[cdt][cdn]
      const terms = (frm.fee_request_terms[row.fee_request] || []).map(
        (term) => term.academic_term
      )
      return { filters: { name: ['in', terms] } }
    })
    frm.set_query('target_fee_request', () => ({
      filters: fee_request_filters,
    }))
  },

  get_terms(frm) {
    if (!frm.doc.scholar) {
      frappe.throw(__('Select the Scholar first.'))
    }

    frappe.prompt(
      [
        {
          fieldname: 'academic_year',
          label: __('Academic Year'),
          fieldtype: 'Link',
          options: 'Academic Year',
          default: frm.doc.academic_year,
          reqd: 1,
        },
        {
          fieldname: 'request_type',
          label: __('Request Type'),
          fieldtype: 'Select',
          options: ['Fees', 'Stipend'],
          default: 'Fees',
          reqd: 1,
        },
        {
          fieldname: 'official_school_name',
          label: __('Official School Name'),
          fieldtype: 'Link',
          options: 'Supplier',
          description: __(
            'Needed only when the terms are owed to more than one school'
          ),
        },
        {
          fieldname: 'amount',
          label: __('Amount'),
          fieldtype: 'Currency',
          description: __('Leave empty to take each term in full'),
        },
      ],
      (values) => {
        frappe
          .call({
            method:
              'education.education.doctype.fee_request.fee_request.get_allocations',
            args: {
              scholar: frm.doc.scholar,
              payment_type: frm.doc.payment_type,
              ...values,
            },
            freeze: true,
          })
          .then((r) => {
            frm.clear_table('allocations')
            for (const allocation of r.message || []) {
              const row = frm.add_child('allocations')
              row.fee_request = allocation.fee_request
              row.academic_term = allocation.academic_term
              row.amount = allocation.amount
            }
            frm.refresh_field('allocations')
            frm.trigger('set_total')
          })
      },
      __('Get Terms'),
      __('Get')
    )
  },

  set_total(frm) {
    const total = (frm.doc.allocations || []).reduce(
      (sum, row) => sum + (row.amount || 0),
      0
    )
    frm.set_value('paid_amount', total)
  },
})

frappe.ui.form.on('Fee Request Payment Allocation', {
  fee_request(frm, cdt, cdn) {
    const row = locals[cdt][cdn]
    frappe.model.set_value(cdt, cdn, 'academic_term', '')
    if (!row.fee_request) {
      return
    }

    get_fee_request_terms(frm, row.fee_request).then((terms) => {
      if (terms.length === 1) {
        frappe.model.set_value(
          cdt,
          cdn,
          'academic_term',
          terms[0].academic_term
        )
      }
    })
  },

  academic_term(frm, cdt, cdn) {
    const row = locals[cdt][cdn]
    const term = (frm.fee_request_terms[row.fee_request] || []).find(
      (term) => term.academic_term === row.academic_term
    )
    if (term && !row.amount) {
      // A refund takes back the term's overpayment; anything else fills what it owes.
      const amount =
        frm.doc.payment_type === 'Refund'
          ? Math.max(-term.outstanding_amount, 0)
          : Math.max(term.outstanding_amount, 0)
      frappe.model.set_value(cdt, cdn, 'amount', amount)
    }
  },

  amount(frm) {
    frm.trigger('set_total')
  },

  allocations_remove(frm) {
    frm.trigger('set_total')
  },
})

// The terms on a Fee Request with their balances, fetched once per request.
function get_fee_request_terms(frm, fee_request) {
  frm.fee_request_terms = frm.fee_request_terms || {}
  if (frm.fee_request_terms[fee_request]) {
    return Promise.resolve(frm.fee_request_terms[fee_request])
  }

  return frappe
    .call({
      method:
        'education.education.doctype.fee_request.fee_request.get_fee_request_terms',
      args: { fee_request },
    })
    .then((r) => {
      frm.fee_request_terms[fee_request] = r.message || []
      return frm.fee_request_terms[fee_request]
    })
}
