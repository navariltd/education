# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

DATA_CORRECTION = "Data correction"
MOVED_TO_ANOTHER_CURRICULUM = "Moved to another curriculum"
FINISHED_SCHOOL = "Finished school"
CURRICULUM_CHANGE_TYPES = (DATA_CORRECTION, MOVED_TO_ANOTHER_CURRICULUM)


class ScholarCurriculumPeriod(Document):
    def validate(self):
        if self.scholar and not self.student_name:
            self.student_name = frappe.db.get_value(
                "Scholar", self.scholar, "student_name"
            )

        if not self.to_date:
            self.validate_single_open_period()

    def validate_single_open_period(self):
        others = frappe.get_all(
            "Scholar Curriculum Period",
            filters={
                "scholar": self.scholar,
                "name": ["!=", self.name],
                "to_date": ["is", "not set"],
            },
            pluck="name",
        )
        if others:
            frappe.throw(
                _("Scholar {0} already has an open curriculum period.").format(
                    self.scholar
                ),
                title=_("Curriculum Period"),
            )


def period_from_date(entry_date=None, year_of_onboarding=None, creation=None):
    """The date a scholar's first curriculum period starts."""
    if entry_date:
        return getdate(entry_date)

    if year_of_onboarding:
        year_start = frappe.db.get_value(
            "Fiscal Year", year_of_onboarding, "year_start_date"
        )
        if year_start:
            return getdate(year_start)

    if creation:
        return getdate(creation)

    return getdate(today())


def open_period(
    scholar,
    from_date,
    promotion_rule,
    class_at_entry,
    source_doctype,
    source_name,
    student_name=None,
):
    """Open the single current curriculum period for a scholar."""
    if get_open_period_names(scholar):
        frappe.throw(
            _("Scholar {0} already has an open curriculum period.").format(scholar),
            title=_("Curriculum Period"),
        )

    if not student_name:
        student_name = frappe.db.get_value("Scholar", scholar, "student_name")

    period = frappe.get_doc(
        {
            "doctype": "Scholar Curriculum Period",
            "scholar": scholar,
            "student_name": student_name,
            "promotion_rule": promotion_rule,
            "from_date": from_date,
            "class_at_entry": class_at_entry,
            "source_doctype": source_doctype,
            "source_name": source_name,
        }
    )
    period.insert(ignore_permissions=True)
    return period


def apply_curriculum_change(
    scholar,
    change_type,
    new_promotion_rule,
    class_at_exit,
    new_current_class,
    class_at_onboarding_changed,
    new_class_at_onboarding,
    source_doctype,
    source_name,
    on_date=None,
):
    """Rewrite the open period, or close it and open the next one."""
    if change_type not in CURRICULUM_CHANGE_TYPES:
        frappe.throw(
            _(
                "Confirm whether this curriculum change is a data correction or a move to another curriculum."
            ),
            title=_("Curriculum Change"),
        )

    period = get_open_period(scholar)
    on_date = getdate(on_date or today())

    if change_type == DATA_CORRECTION:
        period.promotion_rule = new_promotion_rule
        if class_at_onboarding_changed:
            period.class_at_entry = new_class_at_onboarding
        period.source_doctype = source_doctype
        period.source_name = source_name
        period.save(ignore_permissions=True)
        return period

    period = close_period(
        scholar,
        on_date,
        class_at_exit,
        MOVED_TO_ANOTHER_CURRICULUM,
        source_doctype,
        source_name,
    )

    new_period = open_period(
        scholar=scholar,
        from_date=on_date,
        promotion_rule=new_promotion_rule,
        class_at_entry=new_current_class,
        source_doctype=source_doctype,
        source_name=source_name,
        student_name=period.student_name,
    )
    from education.education.doctype.scholar_result.scholar_result import (
        copy_exit_major_as_entry,
    )

    copy_exit_major_as_entry(period.name, new_period)
    return new_period


def close_period(
    scholar, on_date, class_at_exit, end_reason, source_doctype, source_name
):
    """Close the scholar's open curriculum period without opening another."""
    period = get_open_period(scholar)
    period.to_date = getdate(on_date or today())
    period.class_at_exit = class_at_exit
    period.end_reason = end_reason
    period.source_doctype = source_doctype
    period.source_name = source_name
    period.save(ignore_permissions=True)
    return period


def get_open_period(scholar):
    names = get_open_period_names(scholar)
    if len(names) != 1:
        frappe.throw(
            _("Scholar {0} must have one open curriculum period. Found {1}.").format(
                scholar, len(names)
            ),
            title=_("Curriculum Period"),
        )
    return frappe.get_doc("Scholar Curriculum Period", names[0])


def get_open_period_names(scholar):
    return frappe.get_all(
        "Scholar Curriculum Period",
        filters={"scholar": scholar, "to_date": ["is", "not set"]},
        pluck="name",
        order_by="from_date asc",
    )
