# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from frappe import _


class CaseManagement(Document):
	def validate(self):
		if not self.case_manager:
			self.case_manager = frappe.session.user

		if self.case_status == "Closed" and not self.case_closure_date:
			frappe.throw(_("Case Closure Date must be set when Case Status is 'Closed'."))

	def before_submit(self):
		if self.validate_case_type_and_case_plan:
			if not self.case_plan or not self.case_outcome:
				frappe.throw(_("Case Plan and Case Outcome must be filled before submitting."))

		if self.case_status != "Closed":
			frappe.throw(_("Case Status must be 'Closed' before submitting."))

	def on_submit(self):
		update_scholar_status_on_case_close = frappe.db.get_single_value(
			"Education Settings", "update_scholar_status_on_case_close"
		)
		if not update_scholar_status_on_case_close:
			return
		if not self.scholarship_status:
			frappe.throw(
				_("Please specify the scholarship status to be updated on the scholar.")
			)

		# scholar_status = frappe.db.get_value("NL Case Type", self.case_type, "scholar_status")
		if (
			not frappe.db.get_value("Scholar", self.scholar, "status") == self.scholarship_status
		):
			frappe.db.set_value("Scholar", self.scholar, "status", self.scholarship_status)
