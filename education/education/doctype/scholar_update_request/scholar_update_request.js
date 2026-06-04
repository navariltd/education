// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

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
