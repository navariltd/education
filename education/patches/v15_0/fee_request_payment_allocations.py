import frappe


def execute():
    """Move each Fee Request Payment's single Fee Request, term and export line into an
    allocation row, which is where payments now record what they pay."""
    if not frappe.db.has_column("Fee Request Payment", "fee_request"):
        return

    export_line = (
        "frp.export_line"
        if frappe.db.has_column("Fee Request Payment", "export_line")
        else "NULL"
    )
    payments = frappe.db.sql(
        f"""
        SELECT frp.name, frp.docstatus, frp.fee_request, frp.academic_term,
            frp.paid_amount, {export_line} AS export_line
        FROM `tabFee Request Payment` frp
        WHERE IFNULL(frp.fee_request, '') != ''
            AND NOT EXISTS (
                SELECT 1 FROM `tabFee Request Payment Allocation` a
                WHERE a.parent = frp.name AND a.parenttype = 'Fee Request Payment'
            )
        """,
        as_dict=True,
    )
    for payment in payments:
        frappe.get_doc(
            {
                "doctype": "Fee Request Payment Allocation",
                "parent": payment.name,
                "parenttype": "Fee Request Payment",
                "parentfield": "allocations",
                "idx": 1,
                "docstatus": payment.docstatus,
                "fee_request": payment.fee_request,
                "academic_term": payment.academic_term,
                "amount": payment.paid_amount,
                "export_line": payment.export_line,
            }
        ).db_insert()
