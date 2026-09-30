# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ScholarGuardian(Document):
    pass


def validate_unique_guardian_ids(doc):
    """Reject the same ID Number on more than one guardian of this student."""
    seen = {}
    for row in doc.get("guardians") or []:
        id_number = (row.id_number or "").strip()
        row.id_number = id_number
        if not id_number:
            continue

        key = id_number.casefold()
        if key in seen:
            frappe.throw(
                msg=_(
                    "ID Number {0} is already used for a guardian in row {1}. Enter each guardian only once."
                ).format(frappe.bold(id_number), frappe.bold(seen[key])),
                title=_("Duplicate Guardian"),
            )
        seen[key] = row.idx


@frappe.whitelist()
def get_primary_guardian(scholar):
    """The first guardian on a Scholar, in table order."""
    if not scholar or not frappe.db.exists("Scholar", scholar):
        return {}

    if not frappe.flags.ignore_permissions and not frappe.has_permission(
        "Scholar", "read", scholar
    ):
        frappe.throw(
            _("Not permitted to read Scholar {0}").format(scholar),
            frappe.PermissionError,
        )

    rows = frappe.get_all(
        "Scholar Guardian",
        filters={
            "parent": scholar,
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
        limit=1,
    )
    if not rows:
        return {}

    return rows[0]
