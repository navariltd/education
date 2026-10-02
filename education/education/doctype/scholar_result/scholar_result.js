// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholar Result', {
  refresh(frm) {
    const grid = frm.get_field('details').grid
    grid.cannot_add_rows = true
    grid.cannot_delete_rows = true
    if (!frm.doc.details || !frm.doc.details.length) {
      frm.add_child('details')
      frm.refresh_field('details')
    }
    frm.trigger('set_filters')
    frm.trigger('load_result_defaults')
  },

  scholar(frm) {
    frm.set_value('curriculum_period', '')
    frm.trigger('load_result_defaults')
  },

  curriculum_period(frm) {
    frm.trigger('load_result_defaults')
  },

  result_kind(frm) {
    if (
      frm.doc.result_kind !== 'Entry Major' &&
      frm.doc.result_kind !== 'Exit Major'
    ) {
      frm.set_value('exam_type', '')
    }
    if (frm.doc.result_kind !== 'Normal') {
      frm.set_value('academic_term', '')
    }
    apply_result_defaults(frm, frm._result_defaults || {})
  },

  academic_year(frm) {
    if (frm.doc.academic_year && frm.doc.academic_term) {
      frm.set_value('academic_term', '')
    }
    frm.trigger('set_filters')
  },

  exam_type(frm) {
    if (!frm.doc.exam_type || frm.doc.grading_scale) {
      return
    }
    frappe.db
      .get_value('Exam Type', frm.doc.exam_type, 'grading_scale')
      .then((r) => {
        const scale = r.message && r.message.grading_scale
        if (scale && !frm.doc.grading_scale) {
          frm.set_value('grading_scale', scale)
        }
      })
  },

  grading_scale(frm) {
    suggest_grades(frm)
  },

  company(frm) {
    frm.trigger('set_filters')
  },

  set_filters(frm) {
    frm.set_query('scholar', () => ({
      filters: {
        company: frm.doc.company,
      },
    }))
    frm.set_query('curriculum_period', () => ({
      filters: {
        scholar: frm.doc.scholar || '',
      },
    }))
    frm.set_query('academic_term', () => ({
      filters: {
        academic_year: frm.doc.academic_year || '',
      },
    }))
  },

  load_result_defaults(frm) {
    if (!frm.doc.scholar && !frm.doc.curriculum_period) {
      apply_result_layout(frm, {})
      return
    }
    frappe.call({
      method:
        'education.education.doctype.scholar_result.scholar_result.get_result_defaults',
      args: {
        scholar: frm.doc.scholar,
        curriculum_period: frm.doc.curriculum_period,
      },
      callback(r) {
        const defaults = r.message || {}
        frm._result_defaults = defaults
        if (
          defaults.curriculum_period &&
          !frm.doc.curriculum_period &&
          frm.doc.scholar
        ) {
          frm.set_value('curriculum_period', defaults.curriculum_period)
          return
        }
        apply_result_defaults(frm, defaults)
      },
    })
  },
})

frappe.ui.form.on('Scholar Result Detail', {
  score(frm, cdt, cdn) {
    validate_score(cdt, cdn)
    suggest_grade(frm, cdt, cdn)
  },
  maximum_score(frm, cdt, cdn) {
    validate_score(cdt, cdn)
    suggest_grade(frm, cdt, cdn)
  },
})

function apply_result_defaults(frm, defaults) {
  apply_result_layout(frm, defaults)
  if (
    frm.doc.result_kind === 'Exit Major' &&
    defaults.exit_exam_type &&
    !frm.doc.exam_type
  ) {
    frm.set_value('exam_type', defaults.exit_exam_type)
  }
  if (frm.doc.result_kind !== 'Entry Major') {
    if (!frm.doc.class && defaults.current_class) {
      frm.set_value('class', defaults.current_class)
    }
    if (!frm.doc.official_school_name && defaults.official_school_name) {
      frm.set_value('official_school_name', defaults.official_school_name)
    }
  }
  if (
    !frm.doc.grading_scale &&
    frm.doc.result_kind === 'Normal' &&
    defaults.default_grading_scale
  ) {
    frm.set_value('grading_scale', defaults.default_grading_scale)
  }
}

function apply_result_layout(frm, defaults) {
  const kind = frm.doc.result_kind
  const yearly = defaults.result_frequency === 'Academic Year'
  const show_term = kind === 'Normal' && !yearly
  const major = kind === 'Entry Major' || kind === 'Exit Major'
  frm.toggle_display('academic_term', show_term)
  frm.toggle_reqd('academic_term', show_term)
  frm.toggle_display('exam_type', major)
  frm.toggle_reqd('exam_type', major)
  //   frm.set_df_property('exam_type', 'read_only', kind === 'Exit Major' ? 1 : 0)
  if (!show_term && frm.doc.academic_term) {
    frm.set_value('academic_term', '')
  }
}

function suggest_grades(frm) {
  ;(frm.doc.details || []).forEach((row) => {
    suggest_grade(frm, row.doctype, row.name)
  })
}

function validate_score(cdt, cdn) {
  const row = locals[cdt][cdn]
  if (row.maximum_score && flt(row.score) > flt(row.maximum_score)) {
    frappe.throw(__('Score cannot be greater than Maximum Score'))
  }
}

function suggest_grade(frm, cdt, cdn) {
  const row = locals[cdt][cdn]
  if (
    !frm.doc.grading_scale ||
    row.score == null ||
    row.score === '' ||
    !row.maximum_score
  ) {
    return
  }
  frappe.call({
    method: 'education.education.api.get_grade',
    args: {
      grading_scale: frm.doc.grading_scale,
      percentage: (flt(row.score) / flt(row.maximum_score)) * 100,
    },
    callback(r) {
      if (r.message) {
        frappe.model.set_value(cdt, cdn, 'grade', r.message)
      }
    },
  })
}

function flt(value) {
  return parseFloat(value) || 0
}
