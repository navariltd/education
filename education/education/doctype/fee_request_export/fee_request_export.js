// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fee Request Export', {
  onload(frm) {
    frm.ignore_doctypes_on_cancel_all = ['Fee Request']
  },

  refresh(frm) {
    if (frm.doc.docstatus === 1) {
      frm.add_custom_button('Export Fee Requests', () => {
        frappe.prompt(
          [
            {
              fieldname: 'format',
              label: 'Format',
              fieldtype: 'Select',
              options: ['Excel', 'CSV'],
              default: 'Excel',
              reqd: 1,
            },
          ],
          (values) => {
            const format = values.format.toLowerCase()

            const url = `/api/method/education.education.doctype.fee_request_export.fee_request_export.export_fee_requests?export_docname=${frm.doc.name}&format=${format}`

            window.open(url)
          },
          'Export Format'
        )
      })

      if (frm.doc.docstatus === 1) {
        frm.add_custom_button(__('Withdraw Lines'), () =>
          frm.trigger('withdraw_lines')
        )
      }
    }

    frm.set_query('bank_account', () => {
      return {
        filters: {
          company: frm.doc.company,
          is_company_account: 1,
        },
      }
    })
  },

  academic_year: function (frm) {
    frm.trigger('reset_fields')
    frm.set_value('academic_term', '')
    frm.set_query('academic_term', () => {
      return {
        filters: {
          academic_year: frm.doc.academic_year,
        },
      }
    })
  },
  bank: function (frm) {
    frm.trigger('reset_fields')
  },

  company: function (frm) {
    frm.trigger('reset_fields')
  },

  request_type: function (frm) {
    frm.trigger('reset_fields')
  },

  reset_fields(frm) {
    frm.clear_table('kcb_fee_requests')
    frm.clear_table('standard_chartered_fee_requests')
    frm.clear_table('stipend_requests')
    frm.refresh_fields()
  },

  withdraw_lines(frm) {
    const table = {
      Stipend: 'stipend_requests',
      KCB: 'kcb_fee_requests',
      'Standard Chartered': 'standard_chartered_fee_requests',
    }[frm.doc.request_type === 'Stipend' ? 'Stipend' : frm.doc.bank]
    const pending = (frm.doc[table] || []).filter(
      (row) => (row.status || 'Pending') === 'Pending'
    )
    if (!pending.length) {
      frappe.msgprint(__('There are no Pending lines to withdraw.'))
      return
    }

    frappe.prompt(
      [
        {
          fieldname: 'lines',
          label: __('Lines'),
          fieldtype: 'MultiCheck',
          reqd: 1,
          options: pending.map((row) => ({
            label: `${row.idx}: ${row.fee_request} - ${
              row.student_name || ''
            } (${format_currency(row.amount)})`,
            value: row.name,
          })),
        },
        {
          fieldname: 'reason',
          label: __('Reason'),
          fieldtype: 'Small Text',
          reqd: 1,
        },
      ],
      (values) => {
        frm
          .call({
            method: 'withdraw_lines',
            doc: frm.doc,
            args: { lines: values.lines, reason: values.reason },
            freeze: true,
          })
          .then(() => frm.reload_doc())
      },
      __('Withdraw Lines'),
      __('Withdraw')
    )
  },

  get_fee_requests: function (frm) {
    if (
      !frm.doc.academic_year ||
      !frm.doc.academic_term ||
      !frm.doc.company ||
      (frm.doc.request_type !== 'Stipend' && !frm.doc.bank)
    ) {
      frappe.throw(
        __('Please select Academic Year, Academic Term, Company, and Bank.')
      )
    }

    frm
      .call({
        method: 'fetch_fee_requests',
        doc: frm.doc,
        freeze: true,
        freeze_message: __('Fetching fee requests...'),
      })
      .then((r) => {
        if (r.message) {
          if (frm.doc.request_type === 'Stipend') {
            frm.clear_table('stipend_requests')
            for (const fee_request of r.message) {
              const row = frm.add_child('stipend_requests')
              row.fee_request = fee_request.fee_request
              row.scholar = fee_request.scholar
              row.student_name = fee_request.student_name
              row.official_school_name = fee_request.school_name
              row.guardian_name = fee_request.guardian_name
              row.guardian_contact = fee_request.guardian_contact
              row.amount = fee_request.amount
            }
          } else {
            if (frm.doc.bank === 'Standard Chartered') {
              frm.clear_table('standard_chartered_fee_requests')
              for (const fee_request of r.message) {
                const row = frm.add_child('standard_chartered_fee_requests')
                row.fee_request = fee_request.fee_request
                row.scholar = fee_request.scholar
                row.student_name = fee_request.student_name
                row.school_name = fee_request.school_name
                row.account_number = fee_request.account_number
                row.bank_code = fee_request.bank_code
                row.branch_code = fee_request.branch_code
                row.amount = fee_request.amount
                row.email_address = fee_request.email_address
              }
            }

            if (frm.doc.bank === 'KCB') {
              frm.clear_table('kcb_fee_requests')
              for (const fee_request of r.message) {
                const row = frm.add_child('kcb_fee_requests')
                row.fee_request = fee_request.fee_request
                row.scholar = fee_request.scholar
                row.student_name = fee_request.student_name
                row.debit_account = fee_request.debit_account
                row.beneficiary_name = fee_request.beneficiary_name
                row.bank = fee_request.bank
                row.branch = fee_request.branch
                row.branch_bicsort_code = fee_request.branch_bicsort_code
                row.bicsort_code = fee_request.bicsort_code
                row.my_reference = fee_request.my_reference
                row.account_number = fee_request.account_number
                row.amount = fee_request.amount
                row.sms_notification = fee_request.sms_notification
                row.email_notification = fee_request.email_notification
              }
            }
          }

          frm.refresh_fields()
        } else {
          frappe.msgprint(
            __('No fee requests found for the selected criteria.')
          )
        }
      })
  },
})

function export_items_excel(frm) {
  frappe.call({
    method:
      'education.education.doctype.fee_request_export.fee_request_export.export_fee_requests',
    args: {
      export_docname: frm.doc.name,
      format: 'excel',
    },
    callback: function (r) {
      if (r.message) {
        window.open(r.message.file_url)
        frappe.show_alert({
          message: __('Excel file generated successfully'),
          indicator: 'green',
        })
      }
    },
  })
}

function export_items_csv(frm) {
  frappe.call({
    method:
      'education.education.doctype.fee_request_export.fee_request_export.export_fee_requests',
    args: {
      export_docname: frm.doc.name,
      format: 'csv',
    },
    callback: function (r) {
      if (r.message) {
        window.open(r.message.file_url)
        frappe.show_alert({
          message: __('CSV file generated successfully'),
          indicator: 'green',
        })
      }
    },
  })
}
