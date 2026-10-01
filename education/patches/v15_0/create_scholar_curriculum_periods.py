import frappe

from education.education.doctype.scholar_curriculum_period.scholar_curriculum_period import (
    open_period,
    period_from_date,
)


def execute():
    """Open one curriculum period for scholars who do not have one yet."""
    if not frappe.db.table_exists("Scholar Curriculum Period"):
        return

    scholars = frappe.get_all(
        "Scholar",
        fields=[
            "name",
            "student_name",
            "entry_date",
            "year_of_onboarding",
            "creation",
            "promotion_rule",
            "class_at_onboarding",
            "current_class",
        ],
    )

    for scholar in scholars:
        if not scholar.promotion_rule:
            continue

        if frappe.db.exists("Scholar Curriculum Period", {"scholar": scholar.name}):
            continue

        try:
            open_period(
                scholar=scholar.name,
                from_date=period_from_date(
                    scholar.entry_date,
                    scholar.year_of_onboarding,
                    scholar.creation,
                ),
                promotion_rule=scholar.promotion_rule,
                class_at_entry=scholar.class_at_onboarding or scholar.current_class,
                source_doctype="Scholar",
                source_name=scholar.name,
                student_name=scholar.student_name,
            )
        except Exception:
            frappe.log_error(
                title="Scholar Curriculum Period",
                message=frappe.get_traceback(),
            )
