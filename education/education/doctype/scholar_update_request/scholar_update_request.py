# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    cint,
    flt,
    format_datetime,
    formatdate,
    get_datetime,
    getdate,
    nowdate,
)

from education.education.doctype.scholar_guardian.scholar_guardian import (
    validate_unique_guardian_ids,
)

# Scholar fieldname -> Scholar Update Request fieldname
SCHOLAR_FIELD_MAP = {
    "student_name": "student_name",
    "company": "company",
    "circumstance_of_residence": "circumstance_of_residence",
    "donor": "donor",
    "status": "scholarship_status",
    "scholarship_type": "scholarship_type",
    "year_of_onboarding": "year_of_onboarding",
    "entry_date": "entry_date",
    "county": "county",
    "county_abbreviation": "county_abbreviation",
    "sub_county": "sub_county",
    "ward": "ward",
    "class_at_onboarding": "class_at_onboarding",
    "current_class": "current_class",
    "currently_enrolled": "currently_enrolled",
    "promotion_rule": "promotion_rule",
    "official_school_name": "official_school_name",
    "county_of_school": "county_of_school",
    "cohort": "cohort",
    "public_or_private": "public_or_private",
    "day_or_boarding": "day_or_boarding",
    "recommender_name": "recommender_name",
    "recommender_department": "recommender_department",
    "recommender_contact": "recommender_contact",
    "reason_for_recommending": "reason_for_recommending",
    "specific_case_teen_mom": "specific_case_teen_mom",
    "specific_case_diff_abled": "specific_case_diff_abled",
    "date_of_birth": "date_of_birth",
    "birth_certificate_id": "birth_certificate_id",
    "comments": "comments",
}


def normalize_value(value, fieldtype):
    """Bring values from the form and from the database to a comparable form."""
    if value is None or value == "":
        return None

    if fieldtype == "Date":
        return getdate(value)

    if fieldtype in ("Datetime", "Timestamp"):
        return get_datetime(value)

    if fieldtype in ("Int", "Check"):
        return cint(value)

    if fieldtype in ("Currency", "Float", "Percent"):
        return flt(value)

    return str(value).strip()


def display_value(value, fieldtype) -> str:
    """Render a value as plain text for the changes panel."""
    if value is None or value == "":
        return ""

    if fieldtype == "Date":
        return formatdate(value)

    if fieldtype in ("Datetime", "Timestamp"):
        return format_datetime(value)

    return str(value)


class ScholarUpdateRequest(Document):
    def validate(self):
        if self.student_name:
            self.validate_student_name()

        if self.promotion_rule:
            self.validate_promotion_rule()

        if self.class_at_onboarding and cint(
            frappe.db.get_single_value(
                "Education Settings", "validate_class_at_onboarding"
            )
        ):
            self.validate_class_at_onboarding()

        validate_unique_guardian_ids(self)

        if self.scholar:
            self.validate_changes()

    def validate_changes(self):
        if not self.get_changes():
            frappe.throw(
                msg=f"<b>Nothing to update for Scholar {self.scholar}</b><br><br>"
                f"All the details in this request are identical to the ones on the "
                f"Scholar record.<br><br>"
                f"Change at least one detail before saving this request.",
                title="No Changes Detected",
            )

    def get_changes(self) -> list[dict]:
        """The details this request would change on the Scholar."""
        scholar_values = self.get_scholar_values()
        changes = []

        for scholar_field, request_field in SCHOLAR_FIELD_MAP.items():
            field = self.meta.get_field(request_field)
            fieldtype = field.fieldtype if field else "Data"

            current = scholar_values.get(scholar_field)
            proposed = self.get(request_field)

            if normalize_value(current, fieldtype) == normalize_value(
                proposed, fieldtype
            ):
                continue

            changes.append(
                {
                    "fieldname": request_field,
                    "label": _(field.label) if field else request_field,
                    "current": display_value(current, fieldtype),
                    "proposed": display_value(proposed, fieldtype),
                }
            )

        guardian_change = self.get_guardian_change()
        if guardian_change:
            changes.append(guardian_change)

        return changes

    def get_guardian_change(self):
        current = guardian_snapshot(self.get_scholar_guardians())
        proposed = guardian_snapshot(self.guardians)
        if current == proposed:
            return None

        return {
            "fieldname": "guardians",
            "label": _("Guardians"),
            "current": format_guardians(current),
            "proposed": format_guardians(proposed),
        }

    def get_scholar_guardians(self):
        if not frappe.db.table_exists("Scholar Guardian"):
            return []

        return frappe.get_all(
            "Scholar Guardian",
            filters={
                "parent": self.scholar,
                "parenttype": "Scholar",
                "parentfield": "guardians",
            },
            fields=[
                "guardian_name",
                "guardian_contact",
                "id_number",
                "relationship_to_student",
            ],
            order_by="idx asc",
        )

    def get_scholar_values(self):
        scholar_values = frappe.db.get_value(
            "Scholar", self.scholar, list(SCHOLAR_FIELD_MAP.keys()), as_dict=True
        )

        if not scholar_values:
            frappe.throw(
                msg=f"Scholar with Scholar ID: #{self.scholar} does not exist",
                title="Scholar Update Error",
            )

        return scholar_values

    def validate_promotion_rule(self):
        promotion_rule = frappe.get_doc(
            "Scholarship Promotion Rule", self.promotion_rule
        )
        classes = [row.program for row in promotion_rule.eligible_classes]
        if self.current_class not in classes:
            frappe.throw(
                f"Class '{self.current_class}' is not eligible for promotion under the promotion rule '{promotion_rule.name}'."
            )

    def validate_class_at_onboarding(self):
        promotion_rule = frappe.get_doc(
            "Scholarship Promotion Rule", self.promotion_rule
        )
        classes = [row.program for row in promotion_rule.eligible_classes]
        if self.class_at_onboarding not in classes:
            frappe.throw(
                f"The selected Class at Onboarding does not belong to promotion rule '{promotion_rule.name}'."
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

    def on_submit(self):
        self.get_scholar_values()

        values_to_update = {
            scholar_field: self.get(request_field)
            for scholar_field, request_field in SCHOLAR_FIELD_MAP.items()
        }
        values_to_update["entry_date"] = self.entry_date or nowdate()

        frappe.db.set_value("Scholar", self.scholar, values_to_update)
        self.apply_guardians()

        frappe.db.commit()

    def apply_guardians(self):
        """Replace the Scholar's guardians with the rows on this request."""
        if not frappe.db.table_exists("Scholar Guardian"):
            return

        frappe.db.delete(
            "Scholar Guardian",
            {
                "parent": self.scholar,
                "parenttype": "Scholar",
                "parentfield": "guardians",
            },
        )
        for idx, row in enumerate(self.guardians, start=1):
            frappe.get_doc(
                {
                    "doctype": "Scholar Guardian",
                    "parent": self.scholar,
                    "parenttype": "Scholar",
                    "parentfield": "guardians",
                    "idx": idx,
                    "guardian_name": row.guardian_name,
                    "guardian_contact": row.guardian_contact,
                    "id_number": row.id_number,
                    "relationship_to_student": row.relationship_to_student,
                }
            ).db_insert()


@frappe.whitelist()
def get_pending_changes(name: str) -> list[dict]:
    """The changes this request would apply, for the changes panel on the form."""
    doc = frappe.get_doc("Scholar Update Request", name)
    doc.check_permission("read")

    return doc.get_changes()


def guardian_snapshot(rows):
    return [
        (
            (row.guardian_name or "").strip(),
            (row.guardian_contact or "").strip(),
            (row.id_number or "").strip(),
            (row.relationship_to_student or "").strip(),
        )
        for row in rows or []
    ]


def format_guardians(rows) -> str:
    formatted = []
    for name, contact, id_number, relationship in rows:
        details = [part for part in (relationship, contact, id_number) if part]
        if name and details:
            formatted.append(f"{name} ({', '.join(details)})")
        else:
            formatted.append(name or ", ".join(details))
    return "; ".join(formatted)
