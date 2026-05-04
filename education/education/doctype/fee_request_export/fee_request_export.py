# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

import openpyxl
from io import BytesIO, StringIO
from openpyxl.styles import Font, Alignment
import csv


class FeeRequestExport(Document):
	@frappe.whitelist()
	def fetch_fee_requests(self):
		if not self.request_type == "Teen Mom Stipend":
			if self.bank == "KCB" and not self.bank_account:
				frappe.throw("Please select a bank account for KCB.")

		FR = frappe.qb.DocType("Fee Request")
		BA = frappe.qb.DocType("Bank Account")
		SC = frappe.qb.DocType("Scholar")
		CC = frappe.qb.DocType("County Coordinator Mapping Item")

		query = (
			frappe.qb.from_(FR)
			.join(SC)
			.on(FR.scholar == SC.name)
			.left_join(BA)
			.on(FR.official_school_name == BA.party)
			.left_join(CC)
			.on(SC.county == CC.county)
			.select(
				FR.name,
				SC.county,
				SC.guardian_name,
				SC.guardian_contact,
				FR.official_school_name,
				FR.scholar,
				FR.student_name,
				FR.outstanding_amount,
				BA.custom_branch_name,
				BA.branch_code,
				BA.custom_bank_code,
				BA.bank_account_no,
				BA.bank,
				BA.account_name,
				CC.user,
			)
			.where(
				(FR.docstatus == 1)
				& (FR.academic_year == self.academic_year)
				& (FR.academic_term == self.academic_term)
				& (FR.company == self.company)
				& (FR.payment_status.isin(["Unpaid", "Partially Paid"]))
				& ((FR.exported_for_payment == 0) | (FR.exported_for_payment.isnull()))
			)
		)

		if self.request_type == "Teen Mom Stipend":
			query = query.where(FR.request_type == "Teen Mom Stipend")

		fee_requests = query.run(as_dict=True)

		if not fee_requests:
			frappe.throw("No fee requests found.")

		emails = frappe.db.get_value(
			"County Coordinator Mapping",
			"County Coordinator Mapping",
			["payable_email", "scholarship_email"],
			as_dict=True,
		)

		results = []
		if self.request_type == "Teen Mom Stipend":
			for fee_request in fee_requests:
				fee_request_details = {
					"fee_request": fee_request.name,
					"scholar": fee_request.scholar,
					"student_name": fee_request.student_name,
					"school_name": fee_request.official_school_name,
					"guardian_name": fee_request.guardian_name,
					"guardian_contact": fee_request.guardian_contact,
					"amount": fee_request.outstanding_amount,
				}
				results.append(fee_request_details)
		else:
			if self.bank == "Standard Chartered":
				for fee_request in fee_requests:
					fee_request_details = {
						"fee_request": fee_request.name,
						"scholar": fee_request.scholar,
						"student_name": fee_request.student_name,
						"school_name": fee_request.official_school_name,
						"account_number": fee_request.bank_account_no,
						"bank_code": fee_request.custom_bank_code,
						"branch_code": fee_request.branch_code,
						"amount": fee_request.outstanding_amount,
						"email_address": f"{emails.payable_email},{emails.scholarship_email},{fee_request.user}",
					}
					results.append(fee_request_details)

			if self.bank == "KCB":
				company_account = frappe.db.get_value(
					"Bank Account",
					{"name": self.bank_account},
					["bank_account_no", "branch_code"],
					as_dict=True,
				)

				for fee_request in fee_requests:
					fee_request_details = {
						"fee_request": fee_request.name,
						"scholar": fee_request.scholar,
						"student_name": fee_request.student_name,
						"debit_account": (
							company_account.get("bank_account_no") if company_account else None
						),
						"beneficiary_name": fee_request.official_school_name,
						"bank": fee_request.bank,
						"branch": fee_request.custom_branch_name,
						"branch_bicsort_code": (
							company_account.get("branch_code") if company_account else None
						),
						"bicsort_code": fee_request.branch_code,
						"account_number": fee_request.bank_account_no,
						"my_reference": fee_request.official_school_name,
						"sms_notification": fee_request.guardian_contact,
						"amount": fee_request.outstanding_amount,
						"email_notification": f"{emails.scholarship_email}",
					}
					results.append(fee_request_details)

		return results

	def before_save(self):
		if self.request_type == "Teen Mom Stipend":
			self.bank = ""

	def on_submit(self):
		if self.request_type == "Fee Request":
			if self.bank == "Standard Chartered":
				for row in self.standard_chartered_fee_requests:
					if row.fee_request:
						frappe.db.set_value(
							"Fee Request",
							row.fee_request,
							{
								"exported_for_payment": 1,
								"exported_for_payment_on": self.name,
							},
						)

			if self.bank == "KCB":
				for row in self.kcb_fee_requests:
					if row.fee_request:
						frappe.db.set_value(
							"Fee Request",
							row.fee_request,
							{
								"exported_for_payment": 1,
								"exported_for_payment_on": self.name,
							},
						)

		if self.request_type == "Teen Mom Stipend":
			for row in self.stipend_requests:
				if row.fee_request:
					frappe.db.set_value(
						"Fee Request",
						row.fee_request,
						{
							"exported_for_payment": 1,
							"exported_for_payment_on": self.name,
						},
					)

	def on_cancel(self):
		if self.bank == "Standard Chartered":
			for row in self.standard_chartered_fee_requests:
				if row.fee_request:
					frappe.db.set_value(
						"Fee Request",
						row.fee_request,
						{
							"exported_for_payment": 0,
							"exported_for_payment_on": None,
						},
					)

		if self.bank == "KCB":
			for row in self.kcb_fee_requests:
				if row.fee_request:
					frappe.db.set_value(
						"Fee Request",
						row.fee_request,
						{
							"exported_for_payment": 0,
							"exported_for_payment_on": None,
						},
					)


@frappe.whitelist()
def export_fee_requests(export_docname, format="excel"):
	"""Main entry point"""

	doc = frappe.get_doc("Fee Request Export", export_docname)

	if not doc.request_type == "Teen Mom Stipend":
		if not doc.kcb_fee_requests and not doc.standard_chartered_fee_requests:
			frappe.throw("No fee requests to export")

	headers, data = get_headers_and_data(doc)

	if format.lower() == "excel":
		stream_excel(doc.name, headers, data)
	else:
		stream_csv(doc.name, headers, data)


def get_headers_and_data(doc):
	headers = []
	data = []

	if doc.request_type == "Teen Mom Stipend":
		headers = [
			"STUDENT NAME",
			"REFERENCE",
			"OFFICIAL SCHOOL NAME",
			"GUARDIAN NAME",
			"GUARDIAN CONTACT",
			"AMOUNT",
		]

		data = [
			[
				row.student_name,
				row.reference,
				row.official_school_name,
				row.guardian_name,
				row.guardian_contact,
				row.amount,
			]
			for row in doc.stipend_requests
		]
	else:
		if doc.bank == "Standard Chartered":
			headers = [
				"NAME",
				"ACCOUNT NO",
				"BANK CODE",
				"BRANCH CODE",
				"AMOUNT",
				"EMAIL ADDRESS",
				"DETAILS",
			]

			data = [
				[
					row.student_name,
					row.account_number,
					row.bank_code,
					row.branch_code,
					row.amount,
					row.email_address,
					row.details,
				]
				for row in doc.standard_chartered_fee_requests
			]

		elif doc.bank == "KCB":
			headers = [
				"Debit Account",
				"Branch BIC/SORT Code",
				"Beneficiary Name",
				"Bank",
				"Branch",
				"BIC/SORT Code",
				"Account Number",
				"My Reference",
				"Beneficiary Reference",
				"Amount",
				"SMS Notification",
				"Email Notification",
			]

			data = [
				[
					row.debit_account,
					row.branch_bicsort_code,
					row.beneficiary_name,
					row.bank,
					row.branch,
					row.bicsort_code,
					row.account_number,
					row.my_reference,
					row.beneficiary_reference,
					row.amount,
					row.sms_notification,
					row.email_notification,
				]
				for row in doc.kcb_fee_requests
			]

		else:
			frappe.throw("Unsupported bank type")

	return headers, data


def stream_excel(name, headers, data):
	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Fee Requests"

	# Metadata
	ws.append(["Fee Request Export", name])
	ws.append(["Export Date:", frappe.utils.getdate()])
	ws.append([])

	header_font = Font(bold=True)
	header_alignment = Alignment(horizontal="center", vertical="center")

	# Headers
	ws.append(headers)

	header_row = ws.max_row
	for col_num, header in enumerate(headers, 1):
		cell = ws.cell(row=header_row, column=col_num)
		cell.font = header_font
		cell.alignment = header_alignment

	for row in data:
		ws.append(row)

	# Auto column width
	for column in ws.columns:
		max_length = 0
		col_letter = column[0].column_letter

		for cell in column:
			try:
				if cell.value:
					max_length = max(max_length, len(str(cell.value)))
			except Exception as e:  # E722
				frappe.log_error(title="Error while adjusting column width", message=e)

		ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

	output = BytesIO()
	wb.save(output)
	output.seek(0)

	frappe.response.filename = f"{name}_fee_requests.xlsx"
	frappe.response.filecontent = output.getvalue()
	frappe.response.type = "binary"


def stream_csv(name, headers, data):
	output = StringIO()
	writer = csv.writer(output)

	# Metadata
	writer.writerow(["Fee Request Export:", name])
	writer.writerow(["Export Date:", frappe.utils.getdate()])
	writer.writerow([])

	# Headers
	writer.writerow(headers)

	# Data
	writer.writerows(data)

	frappe.response.filename = f"{name}_fee_requests.csv"
	frappe.response.filecontent = output.getvalue()
	frappe.response.type = "csv"
