# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from education.education.doctype.scholar.scholar import is_eligible_status
from education.education.doctype.scholar_guardian.scholar_guardian import (
    get_primary_guardian,
)


class CaseManagement(Document):
    def validate(self):
        self.set_primary_guardian()

        if not self.case_manager:
            self.case_manager = frappe.session.user

        if self.case_status == "Closed" and not self.case_closure_date:
            frappe.throw(
                _("Case Closure Date must be set when Case Status is 'Closed'.")
            )

    def set_primary_guardian(self):
        guardian = get_primary_guardian(self.scholar) if self.scholar else {}
        self.primary_guardian_name = guardian.get("guardian_name")
        self.primary_guardian_contact = guardian.get("guardian_contact")
        self.relationship_to_student = guardian.get("relationship_to_student")

    def before_submit(self):
        if self.validate_case_type_and_case_plan and (
            not self.case_plan or not self.case_outcome
        ):

            frappe.throw(
                _("Case Plan and Case Outcome must be filled before submitting.")
            )

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
        scholar = frappe.db.get_value(
            "Scholar", self.scholar, ["status", "date_of_inactive"], as_dict=True
        )
        values = {}
        if scholar.status != self.scholarship_status:
            values["status"] = self.scholarship_status

        # A scholar who stops being eligible becomes inactive on the case closure date.
        if is_eligible_status(self.scholarship_status):
            if scholar.date_of_inactive:
                values["date_of_inactive"] = None
        elif not scholar.date_of_inactive:
            values["date_of_inactive"] = self.case_closure_date

        if values:
            # Remember what was there so cancelling this case can put it back.
            self.db_set(
                {
                    "scholar_updated": 1,
                    "previous_scholarship_status": scholar.status,
                    "previous_date_of_inactive": scholar.date_of_inactive,
                }
            )
            frappe.db.set_value("Scholar", self.scholar, values)

    def on_cancel(self):
        if not self.scholar_updated:
            return

        current_status = frappe.db.get_value("Scholar", self.scholar, "status")
        if current_status != self.scholarship_status:
            frappe.msgprint(
                _(
                    "Scholar {0} was not restored to {1}: their status was changed to {2} after this case."
                ).format(
                    self.scholar, self.previous_scholarship_status, current_status
                ),
                title=_("Scholar Not Restored"),
                indicator="orange",
            )
            return

        frappe.db.set_value(
            "Scholar",
            self.scholar,
            {
                "status": self.previous_scholarship_status,
                "date_of_inactive": self.previous_date_of_inactive,
            },
        )
        frappe.msgprint(
            _("Scholar {0} was restored to {1}.").format(
                self.scholar, self.previous_scholarship_status
            ),
            indicator="green",
            alert=True,
        )
