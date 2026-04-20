// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports['Scholar Performance Trends'] = {
  filters: [
    {
      fieldname: 'company',
      label: __('Company'),
      fieldtype: 'Link',
      options: 'Company',
      reqd: 1,
      on_change: function () {
        frappe.query_report.set_filter_value('academic_year', '')
        frappe.query_report.set_filter_value('academic_term', '')
      },
    },
    {
      fieldname: 'academic_year',
      label: __('Academic Year'),
      fieldtype: 'Link',
      options: 'Academic Year',
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
      fieldname: 'class',
      label: __('Class'),
      fieldtype: 'Link',
      options: 'Program',
      get_query: function () {
        var company = frappe.query_report.get_filter_value('company')
        return {
          filters: {
            company: company,
          },
        }
      },
    },

    {
      fieldname: 'grading_scale',
      label: __('Grading Scale'),
      fieldtype: 'Link',
      options: 'Grading Scale',
      reqd: 1,
    },
    {
      fieldname: 'average_by',
      label: __('Average By'),
      fieldtype: 'Select',
      options: 'Class\nAcademic Term\nAcademic Year',
      default: 'Class',
      depends_on: 'eval:doc.show_average_performance==1',
    },
    {
      fieldname: 'show_average_performance',
      label: __('Show Average Performance'),
      fieldtype: 'Check',
    },
  ],
}
