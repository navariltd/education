// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fee Request', {
  onload: function (frm) {
    if (frm.is_new()) {
      frm.set_value('paid_amount', 0)
      frm.set_value('adjusted_amount', 0)
      frm.set_value('outstanding_amount', 0)
      frm.set_value('payment_status', 'Unpaid')
      frm.clear_table('payments')
      frm.clear_table('terms')
      frm.refresh_fields(['payments', 'terms'])
    }
  },

  refresh(frm) {
    frm.trigger('set_filters')

    if (frm.doc.docstatus === 0) {
      frm.add_custom_button(__('Copy Lines to Term'), () =>
        frm.trigger('copy_lines_to_term')
      )
    }

    if (frm.doc.docstatus === 1) {
      frm.add_custom_button(__('Refresh Balances'), () =>
        frm
          .call({
            method: 'recalculate_balances',
            doc: frm.doc,
            freeze: true,
          })
          .then(() => frm.reload_doc())
      )

      if (
        !frm.doc.is_supplementary &&
        frm.doc.terms.every((term) => !term.purchase_invoice)
      ) {
        frm.add_custom_button(
          __('Fee Request Payment'),
          () => frm.trigger('make_payment'),
          __('Create')
        )
      }

      frm.add_custom_button(
        __('Supplementary Request'),
        () => frm.trigger('make_supplementary_request'),
        __('Create')
      )
    }
  },

  fee_structure_template: function (frm) {
    if (!frm.doc.fee_structure_template) {
      return
    }

    frappe.prompt(
      [
        {
          fieldname: 'academic_term',
          label: __('Academic Term for these items'),
          fieldtype: 'Link',
          options: 'Academic Term',
          reqd: 1,
          get_query: () => ({
            filters: { academic_year: frm.doc.academic_year },
          }),
        },
      ],
      (values) => {
        frappe.call({
          method:
            'education.education.doctype.fee_request.fee_request.get_fee_structure_template',
          args: {
            fee_structure_template: frm.doc.fee_structure_template,
          },
          callback: function (r) {
            const fee_components = r.message
            if (fee_components) {
              frm.doc.fee_components = (frm.doc.fee_components || []).filter(
                (row) => row.academic_term !== values.academic_term
              )
              frm.doc.fee_components.forEach((row, i) => (row.idx = i + 1))
              for (const component of fee_components) {
                const fee_request_item = frm.add_child('fee_components')
                fee_request_item.academic_term = values.academic_term
                fee_request_item.fees_category = component.fees_category
                fee_request_item.amount = component.amount
              }
              frm.refresh_field('fee_components')
              frm.trigger('set_total_amount')
            }
          },
        })
      },
      __('Fill from Fee Structure')
    )
  },

  academic_year: function (frm) {
    const has_terms = (frm.doc.fee_components || []).some(
      (row) => row.academic_term
    )
    if (has_terms) {
      frappe.msgprint(
        __(
          'Check the Academic Term on each Fee Component: every term must belong to the selected Academic Year.'
        )
      )
    }
  },

  company: function (frm) {
    frm.trigger('set_filters')
  },

  set_filters(frm) {
    frm.set_query('scholar', function () {
      return {
        filters: {
          company: frm.doc.company,
        },
      }
    })

    frm.set_query('fee_structure_template', function () {
      return {
        filters: {
          docstatus: 1,
        },
      }
    })

    frm.set_query('academic_term', 'fee_components', function () {
      return {
        filters: {
          academic_year: frm.doc.academic_year,
        },
      }
    })

    frm.set_query('against_fee_request', function () {
      return {
        filters: {
          docstatus: 1,
          is_supplementary: 0,
          scholar: frm.doc.scholar,
          academic_year: frm.doc.academic_year,
          request_type: frm.doc.request_type,
        },
      }
    })
  },

  set_total_amount(frm) {
    const total_amount = (frm.doc.fee_components || []).reduce(
      (total, item) => total + (item.amount || 0),
      0
    )
    frm.set_value('total_amount', total_amount)
  },

  copy_lines_to_term(frm) {
    const terms = [
      ...new Set(
        (frm.doc.fee_components || [])
          .map((row) => row.academic_term)
          .filter(Boolean)
      ),
    ]
    if (!terms.length) {
      frappe.msgprint(__('Add fee components with an Academic Term first.'))
      return
    }

    frappe.prompt(
      [
        {
          fieldname: 'from_term',
          label: __('Copy From'),
          fieldtype: 'Select',
          options: terms,
          default: terms[0],
          reqd: 1,
        },
        {
          fieldname: 'to_term',
          label: __('Copy To'),
          fieldtype: 'Link',
          options: 'Academic Term',
          reqd: 1,
          get_query: () => ({
            filters: { academic_year: frm.doc.academic_year },
          }),
        },
      ],
      (values) => {
        if (values.from_term === values.to_term) {
          frappe.throw(__('Choose a different term to copy to.'))
        }

        const existing = new Set(
          frm.doc.fee_components
            .filter((row) => row.academic_term === values.to_term)
            .map((row) => row.fees_category)
        )
        frm.doc.fee_components
          .filter((row) => row.academic_term === values.from_term)
          .filter((row) => !existing.has(row.fees_category))
          .forEach((row) => {
            const copy = frm.add_child('fee_components')
            copy.academic_term = values.to_term
            copy.fees_category = row.fees_category
            copy.amount = row.amount
          })
        frm.refresh_field('fee_components')
        frm.trigger('set_total_amount')
      },
      __('Copy Lines to Term')
    )
  },

  make_payment(frm) {
    frappe.new_doc('Fee Request Payment', {
      scholar: frm.doc.scholar,
      academic_year: frm.doc.academic_year,
      fee_request: frm.doc.name,
      academic_term:
        frm.doc.terms.length === 1 ? frm.doc.terms[0].academic_term : '',
    })
  },

  make_supplementary_request(frm) {
    frappe.new_doc('Fee Request', {
      scholar: frm.doc.scholar,
      academic_year: frm.doc.academic_year,
      request_type: frm.doc.request_type,
      is_supplementary: 1,
      against_fee_request: frm.doc.is_supplementary
        ? frm.doc.against_fee_request
        : frm.doc.name,
    })
  },
})

frappe.ui.form.on('Fee Request Item', {
  amount: function (frm) {
    frm.trigger('set_total_amount')
  },

  fee_components_remove: function (frm) {
    frm.trigger('set_total_amount')
  },
})
