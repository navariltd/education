import frappe

PARENT_DOCTYPES = ("Scholar", "Scholar Recruitment", "Scholar Update Request")
DEPRECATED_FIELDS = (
    "guardian_name",
    "guardian_contact",
    "relationship_to_student",
    "column_break_nnqq",
)


def execute():
    for parenttype in PARENT_DOCTYPES:
        _ensure_guardians_migrated(parenttype)
        _drop_deprecated_fields(parenttype)


def _ensure_guardians_migrated(parenttype):
    if not frappe.db.has_column(parenttype, "guardian_name"):
        return

    if not frappe.db.table_exists("Scholar Guardian"):
        frappe.throw(
            f"Scholar Guardian does not exist yet. Run migrate_scholar_guardians before removing fields from {parenttype}."
        )

    pending = frappe.db.sql(
        f"""
		SELECT parent.name
		FROM `tab{parenttype}` parent
		WHERE (
			IFNULL(parent.guardian_name, '') != ''
			OR IFNULL(parent.guardian_contact, '') != ''
			OR IFNULL(parent.relationship_to_student, '') != ''
		)
		AND NOT EXISTS (
			SELECT 1
			FROM `tabScholar Guardian` guardian
			WHERE guardian.parent = parent.name
				AND guardian.parenttype = %s
				AND guardian.parentfield = 'guardians'
		)
		LIMIT 1
		""",
        parenttype,
    )
    if pending:
        frappe.throw(
            f"Guardian details on {parenttype} {pending[0][0]} have not been copied to the Guardians table"
        )


def _drop_deprecated_fields(parenttype):
    table = f"tab{parenttype}"
    for fieldname in DEPRECATED_FIELDS:
        frappe.db.delete("DocField", {"parent": parenttype, "fieldname": fieldname})
        if fieldname in frappe.db.get_table_columns(parenttype):
            frappe.db.sql_ddl(f"alter table `{table}` drop column `{fieldname}`")

    frappe.clear_cache(doctype=parenttype)
    frappe.client_cache.delete_value(f"table_columns::{table}")
