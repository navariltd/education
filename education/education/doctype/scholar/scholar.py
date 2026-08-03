# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc


class Scholar(Document):
    def validate(self):
        if self.student_name:
            self.validate_student_name()

        if self.promotion_rule:
            self.validate_promotion_rule()

        if self.class_at_onboarding:
            self.validate_class_at_onboarding()

    def validate_class_at_onboarding(self):
        promotion_rule = frappe.get_doc(
            "Scholarship Promotion Rule", self.promotion_rule
        )
        classes = [row.program for row in promotion_rule.eligible_classes]
        if self.class_at_onboarding not in classes:
            frappe.throw(
                f"The selected Class at Onboarding does not belong to promotion rule '{promotion_rule.name}'."
            )

    def validate_promotion_rule(self):
        promotion_rule = frappe.get_doc(
            "Scholarship Promotion Rule", self.promotion_rule
        )
        classes = [row.program for row in promotion_rule.eligible_classes]
        if self.current_class not in classes:
            frappe.throw(
                f"Class '{self.current_class}' is not eligible for promotion under the promotion rule '{promotion_rule.name}'."
            )

    def validate_student_name(self):
        name = self.student_name
        valid_pattern = r"^[a-zA-Z\s']+$"

        if not re.match(valid_pattern, name):
            frappe.throw(
                f"<b>Invalid characters in student name</b><br><br>"
                f"<b>Current name:</b> {name}<br><br>"
                f"<b>Allowed characters:</b><br>"
                f"• Letters (A-Z, a-z)<br>"
                f"• Spaces<br>"
                f"• Apostrophes (')<br><br>"
                f"<b>Valid examples:</b><br>"
                f"• John Jim Jones<br>"
                f"• Mary O'Brien<br>"
                f"• Sarah Jane Williams<br><br>"
                f"<b>Invalid examples:</b><br>"
                f"• John123 (contains numbers)<br>"
                f"• Mary-Jane (contains hyphen)<br>"
                f"• James@Smith (contains @)",
                title="Invalid Student Name",
            )

        if re.search(r"\s{2,}", name) or name != name.strip():
            frappe.throw(
                f"<b>Spacing issue in student name</b><br><br>"
                f"<b>Current name:</b> '{name}'<br><br>"
                f"Please ensure:<br>"
                f"• No leading or trailing spaces<br>"
                f"• Only single spaces between names<br><br>"
                f"<b>Correct format:</b> '{name.strip()}'",
                title="Invalid Student Name Format",
            )

        if name != name.title():
            frappe.throw(
                f"<b>Student name must be in Title Case</b><br><br>"
                f"<b>Current:</b> {name}<br>"
                f"<b>Expected:</b> {name.title()}<br><br>"
                f"Each word should start with a capital letter.<br><br>"
                f"<b>Examples:</b><br>"
                f"• john smith → John Smith<br>"
                f"• MARY JONES → Mary Jones<br>"
                f"• james o'brien → James O'Brien",
                title="Invalid Student Name Format",
            )


@frappe.whitelist()
def create_update_request(source_name, target_doc=None):
    return get_mapped_doc(
        "Scholar",
        source_name,
        {
            "Scholar": {
                "doctype": "Scholar Update Request",
                "field_map": {
                    "scholar": "name",
                    "status": "scholarship_status",
                },
            }
        },
        target_doc,
    )
