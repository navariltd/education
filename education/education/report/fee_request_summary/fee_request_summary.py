# Copyright (c) 2026, Navari and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import flt

from education.education.doctype.fee_request.fee_request import (
    get_overall_status,
    get_term_status,
)
from education.education.doctype.scholar.scholar import get_eligible_scholar_statuses

TERM_MEASURES = (
    ("amount", "Amount"),
    ("paid_amount", "Paid"),
    ("outstanding_amount", "Outstanding"),
)
TOTAL_MEASURES = (
    "amount",
    "paid_amount",
    "adjusted_amount",
    "outstanding_amount",
    "in_flight_amount",
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.academic_year:
        frappe.throw(_("Academic Year is required."))

    terms = get_terms(filters)
    return get_columns(filters, terms), get_data(filters, terms)


def get_terms(filters):
    """Terms of the selected academic year, in term order. These become the term columns."""
    term_filters = {"academic_year": filters.academic_year}
    if filters.academic_term:
        term_filters["name"] = filters.academic_term

    terms = frappe.get_all(
        "Academic Term",
        filters=term_filters,
        pluck="name",
        order_by="term_start_date asc, name asc",
    )
    if filters.academic_term and not terms:
        frappe.throw(
            _("Academic Term {0} does not belong to Academic Year {1}.").format(
                filters.academic_term, filters.academic_year
            )
        )
    return terms


def get_columns(filters, terms):
    if filters.consolidate_by_scholar:
        columns = [
            {
                "label": _("Scholar"),
                "fieldname": "scholar",
                "fieldtype": "Link",
                "options": "Scholar",
                "width": 130,
            },
            {
                "label": _("Student Name"),
                "fieldname": "student_name",
                "fieldtype": "Data",
                "width": 180,
            },
            {
                "label": _("Scholarship Status"),
                "fieldname": "scholar_status",
                "fieldtype": "Link",
                "options": "Scholarship Status",
                "width": 160,
            },
            {
                "label": _("Date of Inactive"),
                "fieldname": "date_of_inactive",
                "fieldtype": "Date",
                "width": 120,
            },
            # A scholar who changed schools during the year lists both.
            {
                "label": _("Official School Name"),
                "fieldname": "official_school_name",
                "fieldtype": "Data",
                "width": 220,
            },
            {
                "label": _("Request Type"),
                "fieldname": "request_type",
                "fieldtype": "Data",
                "width": 100,
            },
            {
                "label": _("Payment Method"),
                "fieldname": "payment_method",
                "fieldtype": "Data",
                "width": 150,
            },
            {
                "label": _("Fee Requests"),
                "fieldname": "fee_requests",
                "fieldtype": "Int",
                "width": 110,
            },
        ]
    else:
        columns = [
            {
                "label": _("Fee Request"),
                "fieldname": "fee_request",
                "fieldtype": "Link",
                "options": "Fee Request",
                "width": 140,
            },
            {
                "label": _("Scholar"),
                "fieldname": "scholar",
                "fieldtype": "Link",
                "options": "Scholar",
                "width": 130,
            },
            {
                "label": _("Student Name"),
                "fieldname": "student_name",
                "fieldtype": "Data",
                "width": 180,
            },
            {
                "label": _("Scholarship Status"),
                "fieldname": "scholar_status",
                "fieldtype": "Link",
                "options": "Scholarship Status",
                "width": 160,
            },
            {
                "label": _("Date of Inactive"),
                "fieldname": "date_of_inactive",
                "fieldtype": "Date",
                "width": 120,
            },
            {
                "label": _("Official School Name"),
                "fieldname": "official_school_name",
                "fieldtype": "Link",
                "options": "Supplier",
                "width": 200,
            },
            {
                "label": _("Request Type"),
                "fieldname": "request_type",
                "fieldtype": "Data",
                "width": 100,
            },
            {
                "label": _("Payment Method"),
                "fieldname": "payment_method",
                "fieldtype": "Data",
                "width": 150,
            },
            {
                "label": _("Supplementary"),
                "fieldname": "is_supplementary",
                "fieldtype": "Check",
                "width": 110,
            },
        ]
        if filters.include_drafts:
            columns.append(
                {
                    "label": _("Document Status"),
                    "fieldname": "document_status",
                    "fieldtype": "Data",
                    "width": 120,
                }
            )

    for idx, term in enumerate(terms):
        for measure, label in TERM_MEASURES:
            columns.append(
                {
                    "label": f"{term} {_(label)}",
                    "fieldname": f"term_{idx}_{measure}",
                    "fieldtype": "Currency",
                    "width": 150,
                }
            )

    columns.extend(
        [
            {
                "label": _("Total Amount"),
                "fieldname": "amount",
                "fieldtype": "Currency",
                "width": 130,
            },
            {
                "label": _("Total Paid"),
                "fieldname": "paid_amount",
                "fieldtype": "Currency",
                "width": 130,
            },
            {
                "label": _("Adjusted"),
                "fieldname": "adjusted_amount",
                "fieldtype": "Currency",
                "width": 120,
            },
            {
                "label": _("Total Outstanding"),
                "fieldname": "outstanding_amount",
                "fieldtype": "Currency",
                "width": 140,
            },
            {
                "label": _("At Bank"),
                "fieldname": "in_flight_amount",
                "fieldtype": "Currency",
                "width": 120,
            },
            {
                "label": _("Payment Status"),
                "fieldname": "payment_status",
                "fieldtype": "Data",
                "width": 120,
            },
        ]
    )
    return columns


def get_data(filters, terms):
    if not terms:
        return []

    requests = get_requests(filters)
    if not requests:
        return []

    term_rows = get_term_rows([request.name for request in requests], terms)

    # One group per Fee Request, or per scholar and request type when consolidating.
    # Fees and stipends stay separate so their amounts are never added together.
    groups = {}
    for request in requests:
        rows = term_rows.get(request.name)
        if not rows:
            # The request covers none of the terms shown.
            continue

        payment_method = (
            "Accounting"
            if any(row.purchase_invoice for row in rows.values())
            else "Fee Request Payment"
        )
        if filters.payment_method and payment_method != filters.payment_method:
            continue

        key = (
            (request.scholar, request.request_type)
            if filters.consolidate_by_scholar
            else request.name
        )
        group = groups.setdefault(
            key, frappe._dict(requests=[], payment_methods=set(), terms={})
        )
        group.requests.append(request)
        group.payment_methods.add(payment_method)
        for term, row in rows.items():
            group.terms.setdefault(term, []).append(row)

    data = []
    for group in groups.values():
        line = make_line(group, terms, filters)
        if filters.status and line.payment_status != filters.status:
            continue
        data.append(line)

    if filters.consolidate_by_scholar:
        data.sort(key=lambda line: (line.student_name or "", line.scholar))

    return data


def get_requests(filters):
    FR = DocType("Fee Request")
    SC = DocType("Scholar")
    query = (
        frappe.qb.from_(FR)
        .left_join(SC)
        .on(FR.scholar == SC.name)
        .select(
            FR.name,
            FR.docstatus,
            FR.scholar,
            FR.student_name,
            SC.status.as_("scholar_status"),
            SC.date_of_inactive,
            FR.official_school_name,
            FR.request_type,
            FR.is_supplementary,
        )
        .where(
            (FR.academic_year == filters.academic_year)
            & (FR.docstatus.isin([0, 1] if filters.include_drafts else [1]))
        )
        .orderby(FR.official_school_name)
        .orderby(FR.student_name)
        .orderby(FR.name)
    )
    for fieldname in ("company", "request_type", "scholar", "official_school_name"):
        if filters.get(fieldname):
            query = query.where(FR[fieldname] == filters.get(fieldname))
    if filters.county:
        query = query.where(SC.county == filters.county)

    eligible_statuses = get_eligible_scholar_statuses()
    if filters.eligibility and eligible_statuses:
        if filters.eligibility == "Eligible":
            query = query.where(SC.status.isin(eligible_statuses))
        else:
            query = query.where(SC.status.notin(eligible_statuses))

    return query.run(as_dict=True)


def get_term_rows(fee_requests, terms):
    term_rows = {}
    for row in frappe.get_all(
        "Fee Request Term",
        filters={
            "parenttype": "Fee Request",
            "parent": ["in", fee_requests],
            "academic_term": ["in", terms],
        },
        fields=[
            "parent",
            "academic_term",
            "purchase_invoice",
            *TOTAL_MEASURES,
        ],
    ):
        term_rows.setdefault(row.parent, {})[row.academic_term] = row
    return term_rows


def make_line(group, terms, filters):
    first = group.requests[0]
    line = frappe._dict(
        scholar=first.scholar,
        student_name=first.student_name,
        scholar_status=first.scholar_status,
        date_of_inactive=first.date_of_inactive,
        request_type=first.request_type,
        payment_method=(
            group.payment_methods.pop() if len(group.payment_methods) == 1 else "Mixed"
        ),
    )

    if filters.consolidate_by_scholar:
        line.official_school_name = ", ".join(
            sorted(
                {
                    request.official_school_name
                    for request in group.requests
                    if request.official_school_name
                }
            )
        )
        line.fee_requests = len(group.requests)
    else:
        line.update(
            fee_request=first.name,
            official_school_name=first.official_school_name,
            is_supplementary=first.is_supplementary,
            document_status=_("Draft") if first.docstatus == 0 else _("Submitted"),
        )

    statuses = []
    for measure in TOTAL_MEASURES:
        line[measure] = 0

    for idx, term in enumerate(terms):
        rows = group.terms.get(term)
        if not rows:
            continue

        values = {
            measure: sum(flt(row.get(measure)) for row in rows)
            for measure in TOTAL_MEASURES
        }
        for measure, _label in TERM_MEASURES:
            line[f"term_{idx}_{measure}"] = values[measure]
        for measure in TOTAL_MEASURES:
            line[measure] += values[measure]

        statuses.append(
            get_term_status(
                values["paid_amount"],
                values["adjusted_amount"],
                values["outstanding_amount"],
            )
        )

    line.payment_status = get_overall_status(statuses)
    return line
