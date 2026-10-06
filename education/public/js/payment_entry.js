frappe.ui.form.on('Payment Entry', {
  onload(frm) {
    frm.ignore_doctypes_on_cancel_all = ['Fee Request']
  },
})
