// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholar', {
  refresh: (frm) => {
    if (!frm.is_new() && frm._saved_promotion_rule === undefined) {
      frm._saved_promotion_rule = frm.doc.promotion_rule
    }

    frm.trigger('set_sub_county_filters')
    frm.trigger('set_ward_filters')
    frm.trigger('showSchoolTransferDetails')
    frm.trigger('set_curriculum_class_query')
    frm.trigger('lock_previous_exam')

    if (!frm.doc.__islocal && !frm.is_dirty()) {
      frm.add_custom_button(
        __('Scholar Update Request'),
        () => {
          frappe.model.open_mapped_doc({
            method:
              'education.education.doctype.scholar.scholar.create_update_request',
            frm: frm,
          })
        },
        __('Create')
      )
    }
  },

  after_save(frm) {
    frm._saved_promotion_rule = frm.doc.promotion_rule
  },

  before_save(frm) {
    if (frm.is_new() || frm.doc.promotion_rule === frm._saved_promotion_rule) {
      return
    }

    return new Promise((resolve, reject) => {
      let settled = false
      const dialog = new frappe.ui.Dialog({
        title: __('Curriculum Change'),
        fields: [
          {
            fieldname: 'message',
            fieldtype: 'HTML',
            options: `<p>${__('Curriculum Type is changing from {0} to {1}.', [
              frappe.utils.escape_html(frm._saved_promotion_rule || ''),
              frappe.utils.escape_html(frm.doc.promotion_rule || ''),
            ])}</p><p>${__(
              'A data correction keeps this scholar in the current scholarship curriculum period. A move closes the current period and opens the next one.'
            )}</p>`,
          },
        ],
      })

      const choose = (change_type) => {
        settled = true
        frm.doc.curriculum_change_type = change_type
        if (change_type === 'Moved to another curriculum') {
          frm.doc.class_at_onboarding = frm.doc.current_class
          frm.refresh_field('class_at_onboarding')
        }
        dialog.hide()
        resolve()
      }

      dialog.set_primary_action(__('Moved to another curriculum'), () => {
        choose('Moved to another curriculum')
      })
      dialog.set_secondary_action_label(__('Data correction'))
      dialog.set_secondary_action(() => {
        choose('Data correction')
      })
      dialog.onhide = () => {
        if (!settled) {
          reject()
        }
      }
      dialog.show()
    })
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

  lock_previous_exam(frm) {
    if (frm.is_new()) {
      return
    }
    frappe.db
      .get_value(
        'Scholar Result',
        {
          scholar: frm.doc.name,
          result_kind: 'Entry Major',
          docstatus: 1,
        },
        'name'
      )
      .then((r) => {
        const locked = Boolean(r.message && r.message.name)
        ;[
          'previous_exam_type',
          'previous_exam_year',
          'previous_exam_class',
          'previous_exam_school',
          'previous_exam_grading_scale',
          'previous_maximum_score',
          'previous_score',
          'previous_grade',
        ].forEach((field) => {
          frm.set_df_property(field, 'read_only', locked ? 1 : 0)
        })
      })
  },

  promotion_rule(frm) {
    frm.trigger('set_curriculum_class_query')
    clear_classes_outside_curriculum(frm, [
      'class_at_onboarding',
      'current_class',
    ])
  },

  set_curriculum_class_query(frm) {
    ;['class_at_onboarding', 'current_class'].forEach((field) => {
      frm.set_query(field, () => ({
        query: 'education.education.api.curriculum_program_link_query',
        filters: {
          promotion_rule: frm.doc.promotion_rule || '',
        },
      }))
    })
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

  showSchoolTransferDetails(frm) {
    if (frm.doc.scholar_transfer_details.length) {
      frm.set_df_property('scholar_transfer_details', 'hidden', 0)
    }
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
