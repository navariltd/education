// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholar', {
  refresh: (frm) => {
    frm.trigger('set_sub_county_filters')
    frm.trigger('set_ward_filters')
    frm.trigger('showSchoolTransferDetails')

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
        __('Create'),
      )
    }
  },

  current_class: (frm) => {
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
        },
      })
    }
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
