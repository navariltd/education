// Copyright (c) 2026, Navari Limited and contributors
// For license information, please see license.txt

function eligible_programs(frm) {
  return (frm.doc.eligible_classes || [])
    .map((row) => row.program)
    .filter(Boolean)
}

function set_class_progression_queries(frm) {
  ;['current_class', 'next_class'].forEach((field) => {
    frm.set_query(field, 'class_progression', (doc, cdt, cdn) => {
      const row = locals[cdt] && locals[cdt][cdn]
      const other_class =
        field === 'current_class' ? row?.next_class : row?.current_class
      const programs = eligible_programs(frm).filter(
        (program) => program !== other_class
      )
      if (!programs.length) {
        return {
          query:
            'education.education.doctype.scholarship_promotion_rule.scholarship_promotion_rule.empty_program_search',
        }
      }
      return {
        filters: [['Program', 'name', 'in', programs]],
      }
    })
  })
}

function reject_same_class(cdt, cdn, field) {
  const row = frappe.get_doc(cdt, cdn)
  if (
    !row.current_class ||
    !row.next_class ||
    row.current_class !== row.next_class
  ) {
    return
  }

  frappe.model.set_value(cdt, cdn, field, '')
  frappe.msgprint({
    title: __('Invalid Class Progression'),
    indicator: 'red',
    message: __('Current Class and Next Class cannot be the same in row {0}.', [
      row.idx,
    ]),
  })
}

function clear_ineligible_progression(frm) {
  const programs = new Set(eligible_programs(frm))
  ;(frm.doc.class_progression || []).forEach((row) => {
    ;['current_class', 'next_class'].forEach((field) => {
      if (row[field] && !programs.has(row[field])) {
        frappe.model.set_value(row.doctype, row.name, field, '')
      }
    })
  })
}

frappe.ui.form.on('Scholarship Promotion Rule', {
  onload(frm) {
    if (frm.is_new()) {
      for (const table of [
        'status_progression',
        'eligible_classes',
        'class_progression',
      ]) {
        frm.clear_table(table)
      }
    }
  },
  refresh(frm) {
    set_class_progression_queries(frm)
  },
  eligible_classes_add(frm) {
    set_class_progression_queries(frm)
  },
  eligible_classes_remove(frm) {
    set_class_progression_queries(frm)
    clear_ineligible_progression(frm)
  },
})

frappe.ui.form.on('Eligible Class', {
  program(frm) {
    set_class_progression_queries(frm)
    clear_ineligible_progression(frm)
  },
})

frappe.ui.form.on('Class Progression', {
  current_class(frm, cdt, cdn) {
    reject_same_class(cdt, cdn, 'current_class')
  },
  next_class(frm, cdt, cdn) {
    reject_same_class(cdt, cdn, 'next_class')
  },
  is_final: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn)
    if (row.is_final) {
      frappe.model.set_value(cdt, cdn, 'next_class', '')
    }
  },
})
