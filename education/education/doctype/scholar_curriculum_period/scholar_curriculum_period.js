// Copyright (c) 2026, Navari and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scholar Curriculum Period', {
  refresh(frm) {
    if (!frm.doc.from_date) {
      return
    }

    const end = frm.doc.to_date || frappe.datetime.get_today()
    const span = curriculum_period_span(frm.doc.from_date, end)
    const message = frm.doc.to_date
      ? __('This scholar was in this curriculum for {0}.', [span])
      : __('This scholar has been in this curriculum for {0}.', [span])

    frm.set_intro(message)
  },
})

function curriculum_period_span(from_date, to_date) {
  const start = frappe.datetime.str_to_obj(from_date)
  const end = frappe.datetime.str_to_obj(to_date)
  let years = end.getFullYear() - start.getFullYear()
  let months = end.getMonth() - start.getMonth()
  let days = end.getDate() - start.getDate()

  if (days < 0) {
    months -= 1
    days += new Date(end.getFullYear(), end.getMonth(), 0).getDate()
  }
  if (months < 0) {
    years -= 1
    months += 12
  }

  if (years >= 1) {
    return years === 1 ? __('1 year') : __('{0} years', [years])
  }
  if (months >= 1) {
    return months === 1 ? __('1 month') : __('{0} months', [months])
  }

  const total_days = Math.max(0, frappe.datetime.get_diff(to_date, from_date))
  return total_days === 1 ? __('1 day') : __('{0} days', [total_days])
}
