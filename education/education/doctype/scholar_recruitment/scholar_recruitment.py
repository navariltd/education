# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt
import re

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class ScholarRecruitment(Document):
    def validate(self):
        if self.student_name:
            self.validate_student_name()

        if self.promotion_rule:
            self.validate_promotion_rule()

    def validate_promotion_rule(self):
        promotion_rule = frappe.get_doc(
            "Scholarship Promotion Rule", self.promotion_rule
        )
        if self.current_class not in promotion_rule.eligible_classes:
            frappe.throw(f"Class '{self.current_class}' is not eligible for promotion.")

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

    def on_submit(self):
        scholar = frappe.get_doc(
            {
                "doctype": "Scholar",
                "student_name": self.student_name,
                "company": self.company,
                "circumstance_of_residence": self.circumstance_of_residence,
                "donor": self.donor,
                "status": self.status,
                "scholarship_type": self.scholarship_type,
                "year_of_onboarding": self.year_of_onboarding,
                "entry_date": self.entry_date or nowdate(),
                "county": self.county,
                "county_abbreviation": self.county_abbreviation,
                "sub_county": self.sub_county,
                "ward": self.ward,
                "class_at_onboarding": self.current_class,
                "current_class": self.current_class,
                "currently_enrolled": self.currently_enrolled,
                "promotion_rule": self.promotion_rule,
                "official_school_name": self.official_school_name,
                "county_of_school": self.county_of_school,
                "cohort": self.cohort,
                "public_or_private": self.public_or_private,
                "day_or_boarding": self.day_or_boarding,
                "recommender_name": self.recommender_name,
                "recommender_department": self.recommender_department,
                "recommender_contact": self.recommender_contact,
                "reason_for_recommending": self.reason_for_recommending,
                "specific_case_teen_mom": self.specific_case_teen_mom,
                "specific_case_diff_abled": self.specific_case_diff_abled,
                "guardian_name": self.guardian_name,
                "guardian_contact": self.guardian_contact,
                "relationship_to_student": self.relationship_to_student,
                "scholar_recruitment": self.name,
                "date_of_birth": self.date_of_birth,
                "birth_certificate_id": self.birth_certificate_id,
                "comments": self.comments,
            }
        )
        scholar.insert(ignore_permissions=True)

        frappe.db.commit()
