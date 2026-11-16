import frappe

EXPORT_LINE_DOCTYPES = (
    "KCB Fee Request Export Item",
    "Standard Chartered Fee Request Export Item",
    "Stipend Fee Request Export Item",
)


def execute():
    """Exports used to cover one term set on the export. Record that term in the export's
    terms table and on each of its lines."""
    for export in frappe.get_all(
        "Fee Request Export",
        filters={"academic_term": ["is", "set"]},
        fields=["name", "docstatus", "academic_term", "export_type"],
    ):
        if not frappe.db.exists(
            "Fee Request Export Term",
            {"parent": export.name, "parenttype": "Fee Request Export"},
        ):
            frappe.get_doc(
                {
                    "doctype": "Fee Request Export Term",
                    "parent": export.name,
                    "parenttype": "Fee Request Export",
                    "parentfield": "academic_terms",
                    "idx": 1,
                    "docstatus": export.docstatus,
                    "academic_term": export.academic_term,
                }
            ).db_insert()

        if not export.export_type:
            frappe.db.set_value(
                "Fee Request Export",
                export.name,
                "export_type",
                "Per Term",
                update_modified=False,
            )

    for doctype in EXPORT_LINE_DOCTYPES:
        frappe.db.sql(
            f"""
            UPDATE `tab{doctype}` line
            INNER JOIN `tabFee Request Export` export ON export.name = line.parent
            SET line.academic_term = export.academic_term
            WHERE line.parenttype = 'Fee Request Export'
                AND IFNULL(line.academic_term, '') = ''
            """
        )
