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

  before_save: function (frm, cdt, cdn) {
    if (frm.doc.request_type === 'Teen Mom Stipend') {
      frm.doc.stipend_requests.forEach((row) => {
        let details = `${row.fee_request}|${row.scholar}|${row.student_name}`
        frappe.model.set_value(row.doctype, row.name, 'reference', details)
      })
    } else {
      if (frm.doc.bank === 'Standard Chartered') {
        frm.doc.standard_chartered_fee_requests.forEach((row) => {
          let details = `${row.fee_request}|${row.scholar}|${row.student_name}`
          frappe.model.set_value(row.doctype, row.name, 'details', details)
        })
      }

      if (frm.doc.bank === 'KCB') {
        frm.doc.kcb_fee_requests.forEach((row) => {
          let beneficiary_reference = `${row.fee_request}|${row.scholar}|${row.student_name}`
          frappe.model.set_value(
            row.doctype,
            row.name,
            'beneficiary_reference',
            beneficiary_reference
          )
        })
      }
    }
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

  reset_fields(frm) {
    frm.clear_table('kcb_fee_requests')
    frm.clear_table('standard_chartered_fee_requests')
  },

  get_fee_requests: function (frm) {
    if (
      !frm.doc.academic_year ||
      !frm.doc.academic_term ||
      !frm.doc.company ||
      !frm.doc.bank
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
          if (frm.doc.request_type === 'Teen Mom Stipend') {
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
                row.bicsort_code = fee_request.biscort_code
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
