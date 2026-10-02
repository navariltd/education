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

  previous_exam_type(frm) {
    if (!frm.doc.previous_exam_type || frm.doc.previous_exam_grading_scale) {
      return
    }
    frappe.db
      .get_value('Exam Type', frm.doc.previous_exam_type, 'grading_scale')
      .then((r) => {
        const scale = r.message && r.message.grading_scale
        if (scale && !frm.doc.previous_exam_grading_scale) {
          frm.set_value('previous_exam_grading_scale', scale)
        }
      })
  },

  previous_exam_grading_scale(frm) {
    suggest_previous_grade(frm)
  },

  previous_score(frm) {
    suggest_previous_grade(frm)
  },

  previous_maximum_score(frm) {
    suggest_previous_grade(frm)
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

function suggest_previous_grade(frm) {
  const score = frm.doc.previous_score
  const maximum = frm.doc.previous_maximum_score
  if (
    maximum &&
    score != null &&
    score !== '' &&
    parseFloat(score) > parseFloat(maximum)
  ) {
    frappe.throw(__('Score cannot be greater than Maximum Score'))
  }
  if (
    !frm.doc.previous_exam_grading_scale ||
    score == null ||
    score === '' ||
    !maximum
  ) {
    return
  }
  frappe.call({
    method: 'education.education.api.get_grade',
    args: {
      grading_scale: frm.doc.previous_exam_grading_scale,
      percentage: (parseFloat(score) / parseFloat(maximum)) * 100,
    },
    callback(r) {
      if (r.message) {
        frm.set_value('previous_grade', r.message)
      }
    },
  })
}

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
