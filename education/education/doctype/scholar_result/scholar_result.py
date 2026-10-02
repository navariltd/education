# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from education.education.api import get_grade
from education.education.doctype.scholar_curriculum_period.scholar_curriculum_period import (
    get_open_period,
    get_open_period_names,
)

ENTRY_MAJOR = "Entry Major"
NORMAL = "Normal"
EXIT_MAJOR = "Exit Major"
TERM = "Term"
ACADEMIC_YEAR = "Academic Year"
PREVIOUS_EXAM_FIELDS = (
    "previous_exam_type",
    "previous_exam_year",
    "previous_exam_class",
    "previous_exam_school",
    "previous_exam_grading_scale",
    "previous_maximum_score",
    "previous_score",
    "previous_grade",
)


class ScholarResult(Document):
    def validate(self):
        if not self.result_kind:
            self.result_kind = NORMAL
        self.set_result_context()
        self.validate_outcome()
        self.validate_kind()
        self.validate_period_window()
        self.validate_duplicate()

    def set_result_context(self):
        if not self.curriculum_period:
            frappe.throw(
                _("Select the curriculum period this result belongs to."),
                title=_("Scholar Result"),
            )

        period = frappe.db.get_value(
            "Scholar Curriculum Period",
            self.curriculum_period,
            ["scholar", "promotion_rule"],
            as_dict=True,
        )
        if not period:
            frappe.throw(
                _("Curriculum period {0} was not found.").format(
                    self.curriculum_period
                ),
                title=_("Scholar Result"),
            )
        if period.scholar != self.scholar:
            frappe.throw(
                _("Curriculum period {0} does not belong to scholar {1}.").format(
                    self.curriculum_period, self.scholar
                ),
                title=_("Scholar Result"),
            )

        frequency = frappe.db.get_value(
            "Scholarship Promotion Rule", period.promotion_rule, "result_frequency"
        )
        self.flags.promotion_rule = period.promotion_rule
        self.flags.result_frequency = frequency or TERM

        if self.result_kind == NORMAL:
            self.exam_type = None
            if self.flags.result_frequency == ACADEMIC_YEAR:
                self.academic_term = None
        elif self.result_kind in (ENTRY_MAJOR, EXIT_MAJOR):
            self.academic_term = None

    def validate_outcome(self):
        if len(self.details or []) != 1:
            frappe.throw(
                _("Record one overall mark or grade."),
                title=_("Scholar Result"),
            )

        row = self.details[0]
        normalize_mark(row, "score", "maximum_score")
        validate_mark(row.score, row.maximum_score, row.grade)

        if (
            self.grading_scale
            and row.score is not None
            and row.maximum_score
            and not row.grade
        ):
            row.grade = get_grade(
                self.grading_scale,
                flt(row.score) / flt(row.maximum_score) * 100,
            )

    def validate_kind(self):
        if self.result_kind == NORMAL:
            if self.flags.result_frequency == TERM and not self.academic_term:
                frappe.throw(
                    _("Academic Term is required for a term result."),
                    title=_("Scholar Result"),
                )
            if self.academic_term:
                term_year = frappe.db.get_value(
                    "Academic Term", self.academic_term, "academic_year"
                )
                if term_year != self.academic_year:
                    frappe.throw(
                        _("Academic Term {0} is not in Academic Year {1}.").format(
                            self.academic_term, self.academic_year
                        ),
                        title=_("Scholar Result"),
                    )
            return

        if not self.exam_type:
            frappe.throw(
                _("Exam Type is required for a major result."),
                title=_("Scholar Result"),
            )

        if self.result_kind != EXIT_MAJOR:
            return

        exit_exam_type = frappe.db.get_value(
            "Scholarship Promotion Rule", self.flags.promotion_rule, "exit_exam_type"
        )
        if not exit_exam_type:
            frappe.throw(
                _(
                    "Set an Exit Exam Type on curriculum {0} before recording the final exam."
                ).format(self.flags.promotion_rule),
                title=_("Scholar Result"),
            )
        if self.exam_type != exit_exam_type:
            frappe.throw(
                _("The exit exam for this curriculum is {0}.").format(exit_exam_type),
                title=_("Scholar Result"),
            )

        final_classes = frappe.get_all(
            "Class Progression",
            filters={
                "parent": self.flags.promotion_rule,
                "parenttype": "Scholarship Promotion Rule",
                "is_final": 1,
            },
            pluck="current_class",
        )
        if self.get("class") not in final_classes:
            frappe.throw(
                _(
                    "An exit major can only be recorded for the final class of this curriculum."
                ),
                title=_("Scholar Result"),
            )

    def validate_period_window(self):
        if self.result_kind == ENTRY_MAJOR:
            return

        period = frappe.db.get_value(
            "Scholar Curriculum Period",
            self.curriculum_period,
            ["from_date", "to_date"],
            as_dict=True,
        )
        start, end = self.result_window()
        if not start or not end:
            frappe.throw(
                _("The academic year or term is missing its dates."),
                title=_("Scholar Result"),
            )

        if self.result_kind == EXIT_MAJOR:
            if getdate(end) < getdate(period.from_date):
                frappe.throw(
                    _("This result is before the scholar joined this curriculum."),
                    title=_("Scholar Result"),
                )
            if period.to_date and getdate(end) > getdate(period.to_date):
                frappe.throw(
                    _("This result is after the scholar left this curriculum."),
                    title=_("Scholar Result"),
                )
            return

        if getdate(start) < getdate(period.from_date):
            frappe.throw(
                _("This result is before the scholar joined this curriculum."),
                title=_("Scholar Result"),
            )
        if period.to_date and getdate(end) > getdate(period.to_date):
            frappe.throw(
                _("This result is after the scholar left this curriculum."),
                title=_("Scholar Result"),
            )

    def result_window(self):
        if self.academic_term:
            dates = frappe.db.get_value(
                "Academic Term",
                self.academic_term,
                ["term_start_date", "term_end_date"],
            )
            return dates or (None, None)
        dates = frappe.db.get_value(
            "Academic Year",
            self.academic_year,
            ["year_start_date", "year_end_date"],
        )
        return dates or (None, None)

    def validate_duplicate(self):
        filters = {
            "scholar": self.scholar,
            "curriculum_period": self.curriculum_period,
            "result_kind": self.result_kind,
            "docstatus": 1,
            "name": ["!=", self.name],
        }
        if self.result_kind == NORMAL:
            filters["academic_year"] = self.academic_year
            if self.flags.result_frequency == TERM:
                filters["academic_term"] = self.academic_term

        if frappe.db.exists("Scholar Result", filters):
            frappe.throw(
                _("A {0} result already exists for this curriculum period.").format(
                    self.result_kind
                ),
                title=_("Scholar Result"),
            )


def previous_exam_was_filled(doc):
    normalize_mark(doc, "previous_score", "previous_maximum_score")
    text_fields = [
        field
        for field in PREVIOUS_EXAM_FIELDS
        if field not in ("previous_score", "previous_maximum_score")
    ]
    if any(doc.get(field) not in (None, "") for field in text_fields):
        return True
    return doc.previous_score is not None or bool(doc.previous_grade)


def validate_previous_exam(doc):
    if not previous_exam_was_filled(doc):
        return

    missing = []
    if not doc.previous_exam_type:
        missing.append(_("Exam Type"))
    if not doc.previous_exam_year:
        missing.append(_("Academic Year"))
    if not doc.previous_exam_class:
        missing.append(_("Class"))
    if not doc.previous_exam_school:
        missing.append(_("School"))
    if missing:
        frappe.throw(
            _("Previous Major Exam needs {0}.").format(", ".join(missing)),
            title=_("Previous Major Exam"),
        )

    validate_mark(
        doc.previous_score,
        doc.previous_maximum_score,
        doc.previous_grade,
        title=_("Previous Major Exam"),
    )


def normalize_mark(doc, score_field, maximum_field):
    """An untouched Float is stored as 0. A maximum of 0 is not a maximum."""
    if not doc.get(maximum_field):
        doc.set(maximum_field, None)
        if doc.get(score_field) == 0:
            doc.set(score_field, None)


def validate_mark(score, maximum_score, grade, title=None):
    title = title or _("Scholar Result")
    if score is None and not grade:
        frappe.throw(_("Enter a score or a grade."), title=title)

    if score is not None and not maximum_score:
        frappe.throw(_("Enter a Maximum Score for this score."), title=title)

    if maximum_score is not None and flt(maximum_score) <= 0:
        frappe.throw(_("Maximum Score must be greater than zero."), title=title)

    if score is not None and flt(score) < 0:
        frappe.throw(_("Score cannot be negative."), title=title)

    if score is not None and flt(score) > flt(maximum_score):
        frappe.throw(_("Score cannot be greater than Maximum Score."), title=title)


def create_entry_major_from_previous(doc, scholar):
    """Record the previous major exam on the scholar's open curriculum period."""
    if not previous_exam_was_filled(doc):
        return None

    period = get_open_period(scholar)
    existing = frappe.db.get_value(
        "Scholar Result",
        {
            "scholar": scholar,
            "curriculum_period": period.name,
            "result_kind": ENTRY_MAJOR,
            "docstatus": 1,
        },
        "name",
    )
    if existing:
        return None

    result = frappe.get_doc(
        {
            "doctype": "Scholar Result",
            "scholar": scholar,
            "student_name": doc.student_name,
            "curriculum_period": period.name,
            "result_kind": ENTRY_MAJOR,
            "exam_type": doc.previous_exam_type,
            "academic_year": doc.previous_exam_year,
            "class": doc.previous_exam_class,
            "official_school_name": doc.previous_exam_school,
            "company": doc.company,
            "posting_date": today(),
            "grading_scale": doc.previous_exam_grading_scale,
            "details": [
                {
                    "maximum_score": doc.previous_maximum_score,
                    "score": doc.previous_score,
                    "grade": doc.previous_grade,
                }
            ],
        }
    )
    result.insert(ignore_permissions=True)
    result.submit()
    return result


def copy_exit_major_as_entry(closed_period_name, new_period):
    """Reuse a submitted exit major as the entry major of the next curriculum."""
    exit_name = frappe.db.get_value(
        "Scholar Result",
        {
            "curriculum_period": closed_period_name,
            "result_kind": EXIT_MAJOR,
            "docstatus": 1,
        },
        "name",
    )
    if not exit_name:
        return None

    source = frappe.get_doc("Scholar Result", exit_name)
    detail = source.details[0]
    result = frappe.get_doc(
        {
            "doctype": "Scholar Result",
            "scholar": new_period.scholar,
            "student_name": source.student_name,
            "curriculum_period": new_period.name,
            "result_kind": ENTRY_MAJOR,
            "exam_type": source.exam_type,
            "academic_year": source.academic_year,
            "class": source.get("class"),
            "official_school_name": source.official_school_name,
            "company": source.company,
            "posting_date": today(),
            "grading_scale": source.grading_scale,
            "details": [
                {
                    "maximum_score": detail.maximum_score,
                    "score": detail.score,
                    "grade": detail.grade,
                }
            ],
        }
    )
    result.insert(ignore_permissions=True)
    result.submit()
    return result


@frappe.whitelist()
def get_result_defaults(scholar=None, curriculum_period=None):
    """Form defaults for the open period, or for a period the user already picked."""
    period = None
    if curriculum_period:
        period = frappe.db.get_value(
            "Scholar Curriculum Period",
            curriculum_period,
            ["name", "scholar", "promotion_rule"],
            as_dict=True,
        )
    elif scholar:
        names = get_open_period_names(scholar)
        if len(names) == 1:
            period = frappe.db.get_value(
                "Scholar Curriculum Period",
                names[0],
                ["name", "scholar", "promotion_rule"],
                as_dict=True,
            )

    if not period:
        return {}

    rule = (
        frappe.db.get_value(
            "Scholarship Promotion Rule",
            period.promotion_rule,
            ["result_frequency", "exit_exam_type", "default_grading_scale"],
            as_dict=True,
        )
        or {}
    )
    scholar_values = (
        frappe.db.get_value(
            "Scholar",
            period.scholar,
            ["current_class", "official_school_name"],
            as_dict=True,
        )
        or {}
    )
    exit_exam_grading_scale = None
    if rule.get("exit_exam_type"):
        exit_exam_grading_scale = frappe.db.get_value(
            "Exam Type", rule.exit_exam_type, "grading_scale"
        )

    return {
        "curriculum_period": period.name,
        "scholar": period.scholar,
        "promotion_rule": period.promotion_rule,
        "result_frequency": rule.get("result_frequency") or TERM,
        "exit_exam_type": rule.get("exit_exam_type"),
        "default_grading_scale": rule.get("default_grading_scale"),
        "exit_exam_grading_scale": exit_exam_grading_scale,
        "current_class": scholar_values.get("current_class"),
        "official_school_name": scholar_values.get("official_school_name"),
    }
