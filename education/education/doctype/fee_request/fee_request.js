// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fee Request', {
  onload: function (frm) {
    if (frm.is_new()) {
      frm.set_value('paid_amount', 0)
      frm.set_value('outstanding_amount', 0)
      frm.set_value('payment_status', 'Unpaid')
      frm.set_value('exported_for_payment', 0)
      frm.set_value('exported_for_payment_on', null)
      frm.clear_table('payments')
      frm.refresh_field('payments')
    }
  },

  refresh(frm) {
    frm.trigger('set_filters')
    if (frm.is_new()) {
      frm.set_value('paid_amount', 0)
      frm.set_value('outstanding_amount', 0)
      frm.set_value('payment_status', 'Unpaid')
      frm.clear_table('payments')
      frm.refresh_field('payments')
    }
  },
  fee_structure_template: function (frm) {
    if (frm.doc.fee_structure_template) {
      frm.clear_table('fee_request_items')
      frm.refresh_field('fee_request_items')

      frappe.call({
        method:
          'education.education.doctype.fee_request.fee_request.get_fee_structure_template',
        args: {
          fee_structure_template: frm.doc.fee_structure_template,
        },
        callback: function (r) {
          const fee_components = r.message
          if (fee_components) {
            frm.clear_table('fee_components')
            for (const component of fee_components) {
              const fee_request_item = frm.add_child('fee_components')
              fee_request_item.fees_category = component.fees_category
              fee_request_item.amount = component.amount
            }
            frm.refresh_field('fee_components')
          }
        },
      })
    }
  },

  academic_year: function (frm) {
    if (frm.doc.academic_year) {
      frm.set_value('academic_term', null)
      frm.set_query('academic_term', function () {
        return {
          filters: {
            academic_year: frm.doc.academic_year,
          },
        }
      })
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
  },
})

frappe.ui.form.on('Fee Request Item', {
  amount: function (frm, cdt, cdn) {
    const total_amount = frm.doc.fee_components.reduce((total, item) => {
      return total + (item.amount || 0)
    }, 0)
    frm.set_value('total_amount', total_amount)
    frm.refresh_field('total_amount')
  },
})
