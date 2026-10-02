# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import getdate, today

from education.education.doctype.scholar_curriculum_period.scholar_curriculum_period import (
    CURRICULUM_CHANGE_TYPES,
    MOVED_TO_ANOTHER_CURRICULUM,
    apply_curriculum_change,
    open_period,
    period_from_date,
)
from education.education.doctype.scholar_guardian.scholar_guardian import (
    validate_unique_guardian_ids,
)
from education.education.doctype.scholar_result.scholar_result import (
    create_entry_major_from_previous,
    validate_previous_exam,
)


class Scholar(Document):
    def validate(self):
        if self.student_name:
            self.validate_student_name()

        self.prepare_curriculum_change()

        if self.promotion_rule:
            self.validate_promotion_rule()

        validate_entry_date(self.entry_date)
        validate_unique_guardian_ids(self)
        validate_previous_exam(self)

    def before_save(self):
        change_type = self.curriculum_change_type
        self.flags.curriculum_change_type = change_type
        self.curriculum_change_type = None

        if (
            change_type == MOVED_TO_ANOTHER_CURRICULUM
            and not (self.is_new() or self.flags.in_insert)
            and self.has_value_changed("promotion_rule")
        ):
            self.class_at_onboarding = self.current_class

    def prepare_curriculum_change(self):
        """A move adopts the current class before the curriculum check runs."""
        if self.is_new() or self.flags.in_insert:
            return

        if not self.has_value_changed("promotion_rule"):
            return

        if self.curriculum_change_type not in CURRICULUM_CHANGE_TYPES:
            frappe.throw(
                _(
                    "Confirm whether this curriculum change is a data correction or a move to another curriculum."
                ),
                title=_("Curriculum Change"),
            )

        if self.curriculum_change_type == MOVED_TO_ANOTHER_CURRICULUM:
            self.class_at_onboarding = self.current_class

    def after_insert(self):
        open_period(
            scholar=self.name,
            from_date=period_from_date(
                self.entry_date, self.year_of_onboarding, self.creation
            ),
            promotion_rule=self.promotion_rule,
            class_at_entry=self.class_at_onboarding or self.current_class,
            source_doctype=self.doctype,
            source_name=self.name,
            student_name=self.student_name,
        )
        create_entry_major_from_previous(self, self.name)

    def on_update(self):
        if self.flags.in_insert:
            return

        change_type = self.flags.get("curriculum_change_type")
        if change_type and self.has_value_changed("promotion_rule"):
            apply_curriculum_change(
                scholar=self.name,
                change_type=change_type,
                new_promotion_rule=self.promotion_rule,
                class_at_exit=self.get_value_before_save("current_class"),
                new_current_class=self.current_class,
                class_at_onboarding_changed=self.has_value_changed(
                    "class_at_onboarding"
                ),
                new_class_at_onboarding=self.class_at_onboarding,
                source_doctype=self.doctype,
                source_name=self.name,
            )

        create_entry_major_from_previous(self, self.name)

    def validate_promotion_rule(self):
        promotion_rule = frappe.get_doc(
            "Scholarship Promotion Rule", self.promotion_rule
        )
        classes = [row.program for row in promotion_rule.eligible_classes]
        if self.current_class not in classes:
            frappe.throw(
                f"Class '{self.current_class}' is not eligible for promotion under the promotion rule '{promotion_rule.name}'."
            )
        if self.class_at_onboarding and self.class_at_onboarding not in classes:
            frappe.throw(
                f"Class at Onboarding '{self.class_at_onboarding}' does not belong to the curriculum '{promotion_rule.name}'."
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


def get_eligible_scholar_statuses():
    """Scholarship statuses a scholar must have to be selected."""
    statuses = frappe.db.get_all(
        "Eligible Status",
        filters={
            "parent": "Education Settings",
            "parenttype": "Education Settings",
            "parentfield": "eligible_statuses",
        },
        pluck="status",
    )
    return list(dict.fromkeys(status for status in statuses if status))


def _link_filters(filters):
    if not filters:
        return {}
    if isinstance(filters, dict):
        return dict(filters)

    parsed = {}
    for condition in filters:
        if len(condition) == 4:
            _doctype, fieldname, operator, value = condition
        elif len(condition) == 3:
            fieldname, operator, value = condition
        else:
            continue
        parsed[fieldname] = value if operator == "=" else [operator, value]
    return parsed


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def scholar_query(doctype, txt, searchfield, start, page_len, filters):
    """Link search limited to scholars in an eligible status."""
    eligible_statuses = get_eligible_scholar_statuses()
    if not eligible_statuses:
        return []

    query_filters = _link_filters(filters)
    query_filters.pop("status", None)
    query_filters["status"] = ["in", eligible_statuses]

    or_filters = []
    if txt:
        or_filters = [
            ["name", "like", f"%{txt}%"],
            ["student_name", "like", f"%{txt}%"],
        ]
        if searchfield not in ("name", "student_name"):
            or_filters.append([searchfield, "like", f"%{txt}%"])

    return frappe.get_list(
        "Scholar",
        filters=query_filters,
        or_filters=or_filters,
        fields=["name", "student_name"],
        limit_start=start,
        limit_page_length=page_len,
        order_by="student_name asc, name asc",
        as_list=True,
    )


def validate_entry_date(entry_date):
    """Entry Date can be today or earlier."""
    if entry_date and getdate(entry_date) > getdate(today()):
        frappe.throw(
            _("Entry Date cannot be later than today."),
            title=_("Invalid Entry Date"),
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
                "field_no_map": ["curriculum_change_type"],
            }
        },
        target_doc,
    )
