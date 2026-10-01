// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholar Recruitment', {
  refresh: (frm) => {
    frm.trigger('set_sub_county_filters')
    frm.trigger('set_ward_filters')
    frm.trigger('set_curriculum_class_query')
  },

  promotion_rule(frm) {
    frm.trigger('set_curriculum_class_query')
    clear_classes_outside_curriculum(frm, ['current_class'])
  },

  set_curriculum_class_query(frm) {
    frm.set_query('current_class', () => ({
      query: 'education.education.api.curriculum_program_link_query',
      filters: {
        promotion_rule: frm.doc.promotion_rule || '',
      },
    }))
  },

  county: (frm) => {
    frm.set_value('sub_county', '')
    frm.set_value('ward', '')
    frm.trigger('set_sub_county_filters')
  },

  sub_county: (frm) => {
    frm.trigger('set_ward_filters')
  },

  set_sub_county_filters(frm) {
    frm.set_query('sub_county', () => {
      return {
        filters: {
          county: frm.doc.county,
        },
      }
    })
  },
  set_ward_filters(frm) {
    frm.set_query('ward', () => {
      return {
        filters: {
          sub_county: frm.doc.sub_county,
        },
      }
    })
  },
})

function clear_classes_outside_curriculum(frm, fields) {
  const promotion_rule = frm.doc.promotion_rule
  if (!promotion_rule) {
    fields.forEach((field) => {
      if (frm.doc[field]) {
        frm.set_value(field, '')
      }
    })
    return
  }

  frappe.call({
    method: 'education.education.api.get_curriculum_programs',
    args: { promotion_rule },
    callback(r) {
      if (frm.doc.promotion_rule !== promotion_rule) {
        return
      }
      const programs = r.message || []
      fields.forEach((field) => {
        if (frm.doc[field] && !programs.includes(frm.doc[field])) {
          frm.set_value(field, '')
        }
      })
    },
  })
}
