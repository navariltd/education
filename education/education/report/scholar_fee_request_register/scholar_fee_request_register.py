# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import TypedDict

import frappe
from frappe import _
from frappe.query_builder import DocType


class ScholarFeeRequestRegisterFilters(TypedDict):
    company: str
    academic_year: str
    academic_term: str
    scholar: str
    fee_request: str
    official_school_name: str
    county: str
    circumstance_of_residence: str
    donor: str
    payment_status: str


def execute(filters: ScholarFeeRequestRegisterFilters | None = None):
    return ScholarFeeRequestRegisterReport(filters).run()


class ScholarFeeRequestRegisterReport:
    def __init__(self, filters: ScholarFeeRequestRegisterFilters):
        self.filters = filters

    def run(self):
        self.get_columns()
        self.get_data()
        return self.columns, self.data

    def get_columns(self):
        columns = [
            {
                "label": _("Academic Year"),
                "fieldname": "academic_year",
                "fieldtype": "Link",
                "options": "Academic Year",
                "width": 150,
            },
            {
                "label": _("Academic Term"),
                "fieldname": "academic_term",
                "fieldtype": "Link",
                "options": "Academic Term",
                "width": 150,
            },
            {
                "label": _("Scholar"),
                "fieldname": "scholar",
                "fieldtype": "Link",
                "options": "Scholar",
                "width": 150,
            },
            {
                "label": _("Student Name"),
                "fieldname": "student_name",
                "fieldtype": "Data",
                "width": 200,
            },
            {
                "label": _("Fee Request"),
                "fieldname": "fee_request",
                "fieldtype": "Link",
                "options": "Fee Request",
                "width": 150,
            },
            {
                "label": _("Official School Name"),
                "fieldname": "official_school_name",
                "fieldtype": "Data",
                "width": 200,
            },
            {
                "label": _("Bank"),
                "fieldname": "bank",
                "fieldtype": "Link",
                "options": "Bank",
                "width": 150,
            },
            {
                "label": _("Account Name"),
                "fieldname": "account_name",
                "fieldtype": "Data",
                "width": 200,
            },
            {
                "label": _("Account Number"),
                "fieldname": "account_number",
                "fieldtype": "Data",
                "width": 150,
            },
            {
                "label": _("Branch Code"),
                "fieldname": "branch_code",
                "fieldtype": "Data",
                "width": 150,
            },
            {
                "label": _("Request Type"),
                "fieldname": "request_type",
                "fieldtype": "Data",
                "width": 110,
            },
            {
                "label": _("Amount Requested"),
                "fieldname": "requested_amount",
                "fieldtype": "Currency",
                "width": 140,
            },
            {
                "label": _("Paid"),
                "fieldname": "paid_amount",
                "fieldtype": "Currency",
                "width": 130,
            },
            {
                "label": _("Adjusted"),
                "fieldname": "adjusted_amount",
                "fieldtype": "Currency",
                "width": 130,
            },
            {
                "label": _("Outstanding"),
                "fieldname": "amount",
                "fieldtype": "Currency",
                "width": 140,
            },
            {
                "label": _("At Bank"),
                "fieldname": "in_flight_amount",
                "fieldtype": "Currency",
                "width": 130,
            },
            {
                "label": _("Payment Status"),
                "fieldname": "payment_status",
                "fieldtype": "Data",
                "width": 120,
            },
            {
                "label": _("Purchase Invoice"),
                "fieldname": "purchase_invoice",
                "fieldtype": "Link",
                "options": "Purchase Invoice",
                "width": 150,
            },
        ]

        self.columns = columns

    def get_data(self):
        FR = DocType("Fee Request")
        FRT = DocType("Fee Request Term")
        SC = DocType("Scholar")
        SL = DocType("Supplier")
        BA = DocType("Bank Account")

        query = (
            frappe.qb.from_(FR)
            .join(FRT)
            .on((FRT.parent == FR.name) & (FRT.parenttype == "Fee Request"))
            .left_join(SC)
            .on(FR.scholar == SC.name)
            .left_join(SL)
            .on(FR.official_school_name == SL.name)
            .left_join(BA)
            .on(SL.default_bank_account == BA.name)
            .select(
                FR.name.as_("fee_request"),
                FR.academic_year,
                FRT.academic_term,
                FR.scholar,
                FR.student_name,
                FR.official_school_name,
                FR.request_type,
                FRT.amount.as_("requested_amount"),
                FRT.paid_amount,
                FRT.adjusted_amount,
                FRT.outstanding_amount.as_("amount"),
                FRT.in_flight_amount,
                FRT.payment_status,
                FRT.purchase_invoice,
                SL.supplier_name,
                BA.bank,
                BA.bank_account_no.as_("account_number"),
                BA.account_name,
                BA.branch_code,
            )
            .where(FR.docstatus == 1)
        )

        if self.filters.get("company"):
            query = query.where(FR.company == self.filters.get("company"))
        if self.filters.get("academic_year"):
            query = query.where(FR.academic_year == self.filters.get("academic_year"))
        if self.filters.get("academic_term"):
            query = query.where(FRT.academic_term == self.filters.get("academic_term"))
        if self.filters.get("scholar"):
            query = query.where(FR.scholar == self.filters.get("scholar"))
        if self.filters.get("fee_request"):
            query = query.where(FR.name == self.filters.get("fee_request"))
        if self.filters.get("official_school_name"):
            query = query.where(
                FR.official_school_name == self.filters.get("official_school_name")
            )
        if self.filters.get("county"):
            query = query.where(SC.county == self.filters.get("county"))
        if self.filters.get("circumstance_of_residence"):
            query = query.where(
                SC.circumstance_of_residence
                == self.filters.get("circumstance_of_residence")
            )
        if self.filters.get("donor"):
            query = query.where(SC.donor == self.filters.get("donor"))
        if self.filters.get("payment_status"):
            query = query.where(
                FRT.payment_status == self.filters.get("payment_status")
            )
        else:
            query = query.where(FRT.payment_status != "Paid")

        data = query.run(as_dict=True)

        self.data = data
