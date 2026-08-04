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
      'guardian_name',
      'guardian_contact',
      'relationship_to_student',
      'date_of_birth',
      'birth_certificate_id',
      'comments',
    ]

    fields_to_check.forEach((field) => {
      frm.set_df_property(field, 'read_only', !enabled)
    })

    frm.trigger('set_sub_county_filters')
    frm.trigger('set_ward_filters')
    frm.trigger('showSchoolTransferDetails')
    frm.trigger('render_changes')
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

  current_class: (frm) => {
    frm.trigger('set_promotion_rule_filters')
  },

  scholar: (frm) => {
    frm.trigger('refresh')

    if (!frm.doc.scholar) {
      return
    }

    frappe.db.get_doc('Scholar', frm.doc.scholar).then((scholar) => {
      frm.set_value({
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
        class_at_onboarding: scholar.current_class,
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
        guardian_name: scholar.guardian_name,
        guardian_contact: scholar.guardian_contact,
        relationship_to_student: scholar.relationship_to_student,
        scholar_recruitment: scholar.name,
        date_of_birth: scholar.date_of_birth,
        birth_certificate_id: scholar.birth_certificate_id,
        comments: scholar.comments,
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
  set_promotion_rule_filters(frm) {
    frm.set_value('promotion_rule', '')
    if (frm.doc.current_class) {
      frappe.call({
        method: 'education.education.api.get_eligible_classes',
        args: {
          program: frm.doc.current_class,
        },
        callback: (r) => {
          frm.set_query('promotion_rule', () => {
            return {
              filters: {
                name: ['in', r.message.map((row) => row.parent)],
              },
            }
          })

          if (r.message) {
            frm.set_value('promotion_rule', r.message[0].parent)
          }
        },
      })
    }
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
