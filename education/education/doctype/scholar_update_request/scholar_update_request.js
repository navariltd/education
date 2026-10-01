// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

const PENDING_CHANGES_METHOD =
  'education.education.doctype.scholar_update_request.scholar_update_request.get_pending_changes'

frappe.ui.form.on('Scholar Update Request', {
  refresh: (frm) => {
    const enabled = !!frm.doc.scholar

    fields_to_check = [
      'doctype',
      'student_name',
      'company',
      'circumstance_of_residence',
      'donor',
      'status',
      'scholarship_type',
      'year_of_onboarding',
      'entry_date',
      'county',
      'county_abbreviation',
      'sub_county',
      'ward',
      'class_at_onboarding',
      'current_class',
      'currently_enrolled',
      'promotion_rule',
      'curriculum_change_type',
      'official_school_name',
      'county_of_school',
      'cohort',
      'public_or_private',
      'day_or_boarding',
      'recommender_name',
      'recommender_department',
      'recommender_contact',
      'reason_for_recommending',
      'specific_case_teen_mom',
      'specific_case_diff_abled',
      'date_of_birth',
      'birth_certificate_id',
      'comments',
    ]

    fields_to_check.forEach((field) => {
      frm.set_df_property(field, 'read_only', !enabled)
    })
    frm.set_df_property('guardians', 'read_only', !enabled)

    frm.trigger('set_sub_county_filters')
    frm.trigger('set_ward_filters')
    frm.trigger('showSchoolTransferDetails')
    frm.trigger('render_changes')
    frm.trigger('remember_scholar_promotion_rule')
    frm.trigger('set_curriculum_class_query')
    if (enabled) {
      const classes_locked = !frm.doc.promotion_rule
      frm.set_df_property('class_at_onboarding', 'read_only', classes_locked)
      frm.set_df_property('current_class', 'read_only', classes_locked)
    }
  },

  remember_scholar_promotion_rule(frm) {
    if (!frm.doc.scholar) {
      frm._scholar_promotion_rule = null
      frm.toggle_display('curriculum_change_type', false)
      frm.toggle_reqd('curriculum_change_type', false)
      return
    }

    const scholar = frm.doc.scholar
    frappe.db.get_value('Scholar', scholar, 'promotion_rule').then((r) => {
      if (frm.doc.scholar !== scholar) {
        return
      }
      frm._scholar_promotion_rule = r.message.promotion_rule
      frm.trigger('toggle_curriculum_change_type')
    })
  },

  toggle_curriculum_change_type(frm) {
    if (frm._scholar_promotion_rule == null) {
      return
    }

    const differs =
      frm.doc.promotion_rule &&
      frm.doc.promotion_rule !== frm._scholar_promotion_rule
    frm.toggle_display('curriculum_change_type', differs)
    frm.toggle_reqd('curriculum_change_type', differs)

    if (!differs && frm.doc.curriculum_change_type) {
      frm.set_value('curriculum_change_type', '')
    }
  },

  render_changes(frm) {
    if (frm.is_new() || !frm.doc.scholar) {
      frm.toggle_display('changes_section', false)
      return
    }

    frappe
      .xcall(PENDING_CHANGES_METHOD, { name: frm.doc.name })
      .then((changes) => {
        frm.toggle_display('changes_section', !!changes.length)

        if (changes.length) {
          frm.set_df_property(
            'changes_preview',
            'options',
            changes_html(changes)
          )
        }
      })
  },

  promotion_rule(frm) {
    frm.trigger('toggle_curriculum_change_type')
    frm.trigger('set_curriculum_class_query')
    const classes_locked = !frm.doc.scholar || !frm.doc.promotion_rule
    frm.set_df_property('class_at_onboarding', 'read_only', classes_locked)
    frm.set_df_property('current_class', 'read_only', classes_locked)
    if (frm._loading_scholar) {
      return
    }
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

  curriculum_change_type(frm) {
    if (
      frm.doc.curriculum_change_type === 'Moved to another curriculum' &&
      frm.doc.current_class
    ) {
      frm.set_value('class_at_onboarding', frm.doc.current_class)
    }
  },

  scholar: (frm) => {
    frm.trigger('refresh')

    if (!frm.doc.scholar) {
      frm.clear_table('guardians')
      frm.refresh_field('guardians')
      return
    }

    frappe.db.get_doc('Scholar', frm.doc.scholar).then((scholar) => {
      frm._scholar_promotion_rule = scholar.promotion_rule
      frm._loading_scholar = true
      return frm
        .set_value({
          student_name: scholar.student_name,

          company: scholar.company,
          circumstance_of_residence: scholar.circumstance_of_residence,
          donor: scholar.donor,
          scholarship_status: scholar.status,
          scholarship_type: scholar.scholarship_type,
          year_of_onboarding: scholar.year_of_onboarding,
          entry_date: scholar.entry_date,
          county: scholar.county,
          county_abbreviation: scholar.county_abbreviation,
          sub_county: scholar.sub_county,
          ward: scholar.ward,
          class_at_onboarding: scholar.class_at_onboarding,
          current_class: scholar.current_class,
          currently_enrolled: scholar.currently_enrolled,
          promotion_rule: scholar.promotion_rule,
          official_school_name: scholar.official_school_name,
          county_of_school: scholar.county_of_school,
          cohort: scholar.cohort,
          public_or_private: scholar.public_or_private,
          day_or_boarding: scholar.day_or_boarding,
          recommender_name: scholar.recommender_name,
          recommender_department: scholar.recommender_department,
          recommender_contact: scholar.recommender_contact,
          reason_for_recommending: scholar.reason_for_recommending,
          specific_case_teen_mom: scholar.specific_case_teen_mom,
          specific_case_diff_abled: scholar.specific_case_diff_abled,
          date_of_birth: scholar.date_of_birth,
          birth_certificate_id: scholar.birth_certificate_id,
          comments: scholar.comments,
        })
        .then(() => {
          frm.clear_table('guardians')
          ;(scholar.guardians || []).forEach((row) => {
            const guardian = frm.add_child('guardians')
            guardian.guardian_name = row.guardian_name
            guardian.guardian_contact = row.guardian_contact
            guardian.id_number = row.id_number
            guardian.relationship_to_student = row.relationship_to_student
          })
          frm.refresh_field('guardians')
        })
        .finally(() => {
          frm._loading_scholar = false
        })
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
})

function changes_html(changes) {
  const rows = changes
    .map(
      (change) => `
          <tr>
            <td class="diff-field">${frappe.utils.escape_html(
              change.label
            )}</td>
            <td class="diff-current">${changed_value(change.current)}</td>
            <td class="diff-arrow">&rarr;</td>
            <td class="diff-proposed">${changed_value(change.proposed)}</td>
          </tr>`
    )
    .join('')

  return `
      <style>
        .diff-table {
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 20px;
          font-size: 13px;
        }
        .diff-table thead th {
          text-align: left;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.03em;
          color: var(--text-muted, #8d99a6);
          background: var(--control-bg, #f4f5f6);
          padding: 8px 12px;
          border-bottom: 1px solid var(--border-color, #d1d8dd);
        }
        .diff-table tbody tr {
          border-bottom: 1px solid var(--border-color, #ebeef0);
        }
        .diff-table tbody tr:last-child {
          border-bottom: none;
        }
        .diff-table tbody tr:hover {
          background: var(--control-bg, #f8f9fa);
        }
        .diff-table td {
          padding: 9px 12px;
          vertical-align: middle;
        }
        .diff-field {
          font-weight: 500;
          color: var(--text-color, #1c2126);
          width: 30%;
        }
        .diff-current {
          color: var(--text-muted, #8d99a6);
          text-decoration: line-through;
          text-decoration-color: var(--text-muted, #c9d1d6);
          width: 32%;
        }
        .diff-arrow {
          color: var(--text-muted, #b0b8bf);
          text-align: center;
          width: 6%;
          font-size: 14px;
        }
        .diff-proposed {
          font-weight: 600;
          color: var(--primary, #2e7d32);
          width: 32%;
        }
      </style>
      <table class="diff-table table-bordered">
        <thead>
          <tr>
            <th>${__('Field')}</th>
            <th>${__('Current')}</th>
            <th></th>
            <th>${__('Requested')}</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`
}

function changed_value(value) {
  return value
    ? frappe.utils.escape_html(value)
    : `<span class="text-extra-muted">${__('Empty')}</span>`
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
