// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports['Case Management Summary'] = {
  filters: [
    {
      fieldname: 'company',
      label: __('Company'),
      fieldtype: 'Link',
      options: 'Company',
      reqd: 1,
    },
    {
      fieldname: 'from_date',
      label: __('From Date'),
      fieldtype: 'Date',
      default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
      reqd: 1,
    },
    {
      fieldname: 'to_date',
      label: __('To Date'),
      fieldtype: 'Date',
      default: frappe.datetime.get_today(),
      reqd: 1,
    },

    {
      fieldname: 'scholar',
      label: __('Scholar'),
      fieldtype: 'Link',
      options: 'Scholar',
    },
    {
      fieldname: 'cohort',
      label: __('Cohort'),
      fieldtype: 'Link',
      options: 'Scholarship Cohort',
    },

    {
      fieldname: 'case_management',
      label: __('Case Management'),
      fieldtype: 'Link',
      options: 'Case Management',
    },
    {
      fieldname: 'reason_for_recommending',
      label: __('Reason for Recommending'),
      fieldtype: 'Link',
      options: 'Award Category',
    },
    {
      fieldname: 'case_type',
      label: __('Case Type'),
      fieldtype: 'Link',
      options: 'NL Case Type',
    },
    {
      fieldname: 'case_status',
      label: __('Case Status'),
      fieldtype: 'Select',
      options: 'Pending\nOngoing\nClosed',
    },
    {
      fieldname: 'case_manager',
      label: __('Case Manager'),
      fieldtype: 'Link',
      options: 'User',
    },
  ],
}
