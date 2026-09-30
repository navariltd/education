import frappe

PARENT_DOCTYPES = ("Scholar", "Scholar Recruitment", "Scholar Update Request")


def execute():
    """Copy the single guardian fields into the Guardians child table.

    Leaves guardian_name, guardian_contact, and relationship_to_student in
    place. remove_deprecated_guardian_fields drops those columns later.
    """
    if not frappe.db.table_exists("Scholar Guardian"):
        return

    for parenttype in PARENT_DOCTYPES:
        _migrate_parent(parenttype)


def _migrate_parent(parenttype):
    if not frappe.db.has_column(parenttype, "guardian_name"):
        return

    records = frappe.db.sql(
        f"""
		SELECT
			name,
			guardian_name,
			guardian_contact,
			relationship_to_student
		FROM `tab{parenttype}`
		WHERE IFNULL(guardian_name, '') != ''
			OR IFNULL(guardian_contact, '') != ''
			OR IFNULL(relationship_to_student, '') != ''
		""",
        as_dict=True,
    )

    for record in records:
        if frappe.db.exists(
            "Scholar Guardian",
            {
                "parent": record.name,
                "parenttype": parenttype,
                "parentfield": "guardians",
            },
        ):
            continue

        frappe.get_doc(
            {
                "doctype": "Scholar Guardian",
                "parent": record.name,
                "parenttype": parenttype,
                "parentfield": "guardians",
                "idx": 1,
                "guardian_name": record.guardian_name,
                "guardian_contact": record.guardian_contact,
                "relationship_to_student": record.relationship_to_student,
            }
        ).db_insert()
