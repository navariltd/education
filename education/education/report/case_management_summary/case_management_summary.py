# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import TypedDict
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import getdate


@dataclass
class CaseManagementSummaryFilters:
    from_date: str
    to_date: str
    scholar: str
    company: str
    case_management: str
    reason_for_recommending: str
    cohort: str
    case_type: str
    case_status: str
    case_manager: str


def execute(filters: CaseManagementSummaryFilters | None = None):
    return CaseManagementSummary(filters).run()


class CaseManagementSummary:

    def __init__(self, filters: CaseManagementSummaryFilters | None):
        self.filters = filters
        self.from_date = getdate(filters.get("from_date"))
        self.to_date = getdate(filters.get("to_date"))
        self.data = []
        self.columns = []

    def run(self):
        if not self.columns:
            self.columns = self.get_columns()

        self.data = self.get_data()

        return self.columns, self.data

    def get_data(self):
        CM = frappe.qb.DocType("Case Management")

        query = (
            frappe.qb.from_(CM)
            .select(
                CM.scholar,
                CM.student_name,
                CM.company,
                CM.official_school_name,
                CM.case_type,
                CM.case_status,
                CM.case_manager,
                CM.case_manager_name,
                CM.case_report_date,
                CM.case_closure_date,
            )
            .where(
                (CM.case_report_date >= self.from_date)
                & (CM.case_report_date <= self.to_date)
            )
            .where(CM.company == self.filters.get("company"))
        )

        if self.filters.get("scholar"):
            query = query.where(CM.scholar == self.filters.get("scholar"))

        if self.filters.get("case_management"):
            query = query.where(CM.name == self.filters.get("case_management"))

        if self.filters.get("reason_for_recommending"):
            query = query.where(
                CM.reason_for_recommending
                == self.filters.get("reason_for_recommending")
            )

        if self.filters.get("cohort"):
            query = query.where(CM.cohort == self.filters.get("cohort"))

        if self.filters.get("case_type"):
            query = query.where(CM.case_type == self.filters.get("case_type"))

        if self.filters.get("case_status"):
            query = query.where(CM.case_status == self.filters.get("case_status"))

        if self.filters.get("case_manager"):
            query = query.where(CM.case_manager == self.filters.get("case_manager"))

        return query.run(as_dict=1)

    def get_columns(self):
        columns = [
            {
                "label": "Scholar ID",
                "fieldname": "scholar",
                "fieldtype": "Link",
                "options": "Scholar",
                "width": "200",
            },
            {
                "label": "Student Name",
                "fieldname": "student_name",
                "fieldtype": "Data",
                "width": "200",
            },
            {
                "label": "Official School Name",
                "fieldname": "official_school_name",
                "fieldtype": "Link",
                "options": "Supplier",
                "width": "250",
            },
            {
                "label": "Case Type",
                "fieldname": "case_type",
                "fieldtype": "Link",
                "options": "NL Case Type",
                "width": "250",
            },
            {
                "label": "Case Status",
                "fieldname": "case_status",
                "fieldtype": "Data",
                "width": "150",
            },
            {
                "label": "Case Manager",
                "fieldname": "case_manager_name",
                "fieldtype": "Data",
                "width": "150",
            },
            {
                "label": "Case Report Date",
                "fieldname": "case_report_date",
                "fieldtype": "Date",
                "width": "150",
            },
            {
                "label": "Case Closure Date",
                "fieldname": "case_closure_date",
                "fieldtype": "Date",
                "width": "150",
            },
        ]

        return columns
