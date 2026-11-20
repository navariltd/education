import frappe


def execute():
    """The "Fee Request" request type is now called "Fees"."""
    for doctype in ("Fee Request", "Fee Request Export", "Fee Request Payment Import"):
        frappe.db.sql(
            f"""
            UPDATE `tab{doctype}`
            SET request_type = 'Fees'
            WHERE request_type = 'Fee Request' OR IFNULL(request_type, '') = ''
            """
        )
