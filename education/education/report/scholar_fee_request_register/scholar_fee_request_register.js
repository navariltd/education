// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports['Scholar Fee Request Register'] = {
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
        let academic_year =
          frappe.query_report.get_filter_value('academic_year')
        frappe.query_report.set_filter_value('academic_term', '')
        frappe.query_report.refresh()
        frappe.query_report.set_filter_query('academic_term', function () {
          return {
            filters: {
              academic_year: academic_year,
            },
          }
        })
      },
    },
    {
      fieldname: 'academic_term',
      label: __('Academic Term'),
      fieldtype: 'Link',
      options: 'Academic Term',
      reqd: 1,
      get_query: function () {
        var academic_year =
          frappe.query_report.get_filter_value('academic_year')
        return {
          filters: {
            academic_year: academic_year,
          },
        }
      },
    },
    {
      fieldname: 'scholar',
      label: __('Scholar'),
      fieldtype: 'Link',
      options: 'Scholar',
    },
    {
      fieldname: 'fee_request',
      label: __('Fee Request'),
      fieldtype: 'Link',
      options: 'Fee Request',
    },
    {
      fieldname: 'official_school_name',
      label: __('Official School Name'),
      fieldtype: 'Link',
      options: 'Supplier',
    },
    {
      fieldname: 'county',
      label: __('County'),
      fieldtype: 'Link',
      options: 'NL County',
    },
    {
      fieldname: 'circumstance_of_residence',
      label: __('Circumstance of Residence'),
      fieldtype: 'Link',
      options: 'Circumstance of Residence',
    },
    {
      fieldname: 'donor',
      label: __('Donor'),
      fieldtype: 'Link',
      options: 'Donor',
    },
    {
      fieldname: 'payment_status',
      label: __('Payment Status'),
      fieldtype: 'Select',
      description: __('Leave empty to show everything not fully paid'),
      options: [
        { value: '', label: '' },
        { value: 'Unpaid', label: __('Unpaid') },
        { value: 'Partially Paid', label: __('Partially Paid') },
        { value: 'Paid', label: __('Paid') },
        { value: 'Overpaid', label: __('Overpaid') },
      ],
    },
  ],
}
