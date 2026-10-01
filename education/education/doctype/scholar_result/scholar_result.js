// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholar Result', {
  refresh: function (frm) {
    frm.get_field('details').grid.cannot_add_rows = true
    frm.trigger('set_filters')
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
  },

  grading_scale: function (frm) {
    if (frm.doc.grading_scale) {
      frappe.model.clear_table(frm.doc, 'details')
      var row = frm.add_child('details')
      row.maximum_score = 100
      frm.refresh_field('details')
    }
  },
})

frappe.ui.form.on('Scholar Result Detail', {
  score: function (frm, cdt, cdn) {
    var d = locals[cdt][cdn]

    if (!frm.doc.grading_scale) {
      d.score = ''
      frappe.throw(
        __('Please fill in all the details to generate Scholar Result.')
      )
    }

    if (d.score > 100) {
      frappe.throw(__('Score cannot be greater than 100'))
    } else {
      frappe.call({
        method: 'education.education.api.get_grade',
        args: {
          grading_scale: frm.doc.grading_scale,
          percentage: (d.score / d.maximum_score) * 100,
        },
        callback: function (r) {
          if (r.message) {
            frappe.model.set_value(cdt, cdn, 'grade', r.message)
          }
        },
      })
    }
  },
})
