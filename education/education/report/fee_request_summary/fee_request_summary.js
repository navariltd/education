// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.query_reports['Fee Request Summary'] = {
  filters: [
    {
      fieldname: 'company',
      label: __('Organization'),
      fieldtype: 'Link',
      options: 'Company',
      default: frappe.defaults.get_user_default('company'),
      reqd: 1,
    },
    {
      fieldname: 'academic_year',
      label: __('Academic Year'),
      fieldtype: 'Link',
      options: 'Academic Year',
      default: frappe.defaults.get_user_default('academic_year'),
      reqd: 1,
      on_change: function () {
        frappe.query_report.set_filter_value('academic_term', '')
      },
    },
    {
      fieldname: 'academic_term',
      label: __('Academic Term'),
      fieldtype: 'Link',
      options: 'Academic Term',
      description: __('Leave empty to show every term of the Academic Year'),
      get_query: function () {
        return {
          filters: {
            academic_year:
              frappe.query_report.get_filter_value('academic_year'),
          },
        }
      },
    },
    {
      fieldname: 'status',
      label: __('Payment Status'),
      fieldtype: 'Select',
      options: ['', 'Unpaid', 'Partially Paid', 'Paid', 'Overpaid'],
    },
    {
      fieldname: 'official_school_name',
      label: __('Official School Name'),
      fieldtype: 'Link',
      options: 'Supplier',
    },
    {
      fieldname: 'request_type',
      label: __('Request Type'),
      fieldtype: 'Select',
      options: ['', 'Fees', 'Stipend'],
    },
    {
      fieldname: 'payment_method',
      label: __('Payment Method'),
      fieldtype: 'Select',
      options: ['', 'Accounting', 'Fee Request Payment'],
    },
    {
      fieldname: 'scholar',
      label: __('Scholar'),
      fieldtype: 'Link',
      options: 'Scholar',
    },
    {
      fieldname: 'county',
      label: __('County'),
      fieldtype: 'Link',
      options: 'NL County',
    },
    {
      fieldname: 'eligibility',
      label: __('Scholar Eligibility'),
      fieldtype: 'Select',
      options: ['', 'Eligible', 'Not Eligible'],
      description: __('Based on the Eligible Statuses in Education Settings'),
    },
    {
      fieldname: 'include_drafts',
      label: __('Include Drafts'),
      fieldtype: 'Check',
      default: 0,
    },
    {
      fieldname: 'consolidate_by_scholar',
      label: __('Consolidate by Scholar'),
      fieldtype: 'Check',
      default: 0,
      description: __(
        'One row per scholar, adding up all their Fee Requests. Fees and stipends stay on separate rows.'
      ),
    },
  ],

  formatter: function (value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data)
    if (column.fieldname === 'payment_status' && data) {
      const color = {
        Paid: 'green',
        'Partially Paid': 'orange',
        Unpaid: 'red',
        Overpaid: 'blue',
      }[data.payment_status]
      if (color) {
        value = `<span class="indicator-pill ${color}">${value}</span>`
      }
    }
    return value
  },
}
