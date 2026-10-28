import json

import frappe

CUSTOM_FIELD = "custom_date_of_inactive"


def execute():
    """Replace the site's custom "Date of Inactive" field with the standard date_of_inactive."""
    if frappe.db.has_column("Scholar", CUSTOM_FIELD):
        frappe.db.sql(
            f"""
            UPDATE `tabScholar`
            SET date_of_inactive = `{CUSTOM_FIELD}`
            WHERE date_of_inactive IS NULL AND `{CUSTOM_FIELD}` IS NOT NULL
            """
        )

    # Customize Form saved a field order that names the custom field.
    for setter in frappe.get_all(
        "Property Setter",
        filters={"doc_type": "Scholar", "property": "field_order"},
        fields=["name", "value"],
    ):
        order = json.loads(setter.value or "[]")
        if CUSTOM_FIELD not in order:
            continue
        if "date_of_inactive" in order:
            order.remove(CUSTOM_FIELD)
        else:
            order[order.index(CUSTOM_FIELD)] = "date_of_inactive"
        frappe.db.set_value("Property Setter", setter.name, "value", json.dumps(order))

    for script in frappe.get_all(
        "Server Script",
        filters={"disabled": 0, "script": ["like", f"%{CUSTOM_FIELD}%"]},
        pluck="name",
    ):
        frappe.db.set_value("Server Script", script, "disabled", 1)

    custom_field = frappe.db.get_value(
        "Custom Field", {"dt": "Scholar", "fieldname": CUSTOM_FIELD}
    )
    if custom_field:
        frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True)
