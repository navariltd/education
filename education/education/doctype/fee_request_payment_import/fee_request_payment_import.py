# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import csv
import openpyxl

import frappe
from frappe.model.document import Document

from frappe.utils.file_manager import get_file_path


class FeeRequestPaymentImport(Document):
	def before_save(self):
		if self.payments:
			total_amount = sum(p.amount for p in self.payments)
			self.total_amount = total_amount

		if self.request_type == "Teen Mom Stipend":
			self.bank = ""

	def on_submit(self):
		if not self.payments:
			frappe.throw("No payments to process.")

		for payment in self.payments:
			try:
				frp = frappe.get_doc(
					{
						"doctype": "Fee Request Payment",
						"fee_request": payment.fee_request,
						"scholar": payment.scholar,
						"paid_amount": payment.amount,
						"academic_year": self.academic_year,
						"academic_term": self.academic_term,
						"fee_request_payment_import": self.name,
					}
				)
				frp.save(ignore_permissions=True)
				frp.submit()
				payment.db_set("payment_created", True)
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "Payment Record Creation Failed")


@frappe.whitelist()
def process_payment_file(docname):
	doc = frappe.get_doc("Fee Request Payment Import", docname)

	if not doc.payment_file:
		frappe.throw("Please attach a payment file.")

	doc.status = "Processing"
	doc.save(ignore_permissions=True)

	try:
		file_path = get_file_path(doc.payment_file)
		rows = read_file(file_path)
		# bank = doc.bank

		payments = parse_file(rows, doc)

		doc.set("payments", [])  # Clear existing payments if any
		for payment in payments:
			doc.append("payments", payment)

		doc.status = "Completed"
		doc.save(ignore_permissions=True)
	except Exception as e:
		doc.status = "Failed"
		doc.save(ignore_permissions=True)
		frappe.log_error(frappe.get_traceback(), "Payment Import Failed")
		frappe.throw(str(e))


def read_file(file_path):
	if file_path.endswith(".csv"):
		with open(file_path, newline="", encoding="utf-8") as f:
			return list(csv.reader(f))

	elif file_path.endswith(".xlsx"):
		wb = openpyxl.load_workbook(file_path)
		ws = wb.active
		return [[cell.value for cell in row] for row in ws.iter_rows()]

	else:
		frappe.throw("Unsupported file format")


def parse_file(rows, doc):
	if not doc.request_type == "Teen Mom Stipend":
		if doc.bank == "KCB":
			return parse_kcb(rows)
		elif doc.bank == "Standard Chartered":
			return parse_standard_chartered(rows)
		else:
			frappe.throw("Unsupported bank")
	else:
		return parse_teen_mom_stipend(rows)


# KCB
def parse_kcb(rows):
	header_index, headers = find_header_index(rows, "Description", bank="KCB")
	idx = {h: i for i, h in enumerate(headers)}

	data = []
	for row in rows[header_index + 1 :]:
		if not any(row):
			continue

		description = row[idx["Description"]]
		parsed = parse_kcb_description(description)
		if not parsed:
			continue

		details = parsed.get("beneficiary_reference").split("|")
		amount = parsed.get("transfer_amount")
		if isinstance(amount, str):
			amount = amount.replace(",", "").replace(" KES", "").replace("Sh", "").strip()
			amount = float(amount) if amount else 0
		else:
			amount = float(amount or 0)
		data.append(
			{
				"scholar": details[1] if len(details) > 1 else None,
				"fee_request": details[0] if len(details) > 0 else None,
				"amount": amount,
			}
		)

	return data


def parse_kcb_description(description):
	"""
	Convert multi-line description into dict
	"""
	result = {}

	if not description:
		return result

	lines = description.split("\n")

	for line in lines:
		if ":" not in line:
			continue

		key, value = line.split(":", 1)
		key = key.strip().lower().replace(" ", "_")
		value = value.strip()

		result[key] = value

	return result


# Standard Chartered
def parse_standard_chartered(rows):
	header_index, headers = find_header_index(
		rows, "Payment Details in English 1", bank="Standard Chartered"
	)
	idx = {h: i for i, h in enumerate(headers)}

	data = []
	for row in rows[header_index + 1 :]:
		if not any(row):
			continue

		if (
			row[idx["Payment Details in English 1"]] == ""
			or row[idx["Payment Details in English 1"]] is None
		):
			continue

		details = row[idx["Payment Details in English 1"]].split("|")
		amount = row[idx["Payment Amount"]]
		if isinstance(amount, str):
			amount = amount.replace(",", "").replace(" KES", "").replace("Sh", "").strip()
			amount = float(amount) if amount else 0
		else:
			amount = float(amount or 0)
		data.append(
			{
				"scholar": details[1] if len(details) > 1 else None,
				"fee_request": details[0] if len(details) > 0 else None,
				"amount": amount,
			}
		)

	return data


def parse_teen_mom_stipend(rows):
	header_index, headers = find_header_index(rows, "REFERENCE")
	idx = {h: i for i, h in enumerate(headers)}

	data = []
	for row in rows[header_index + 1 :]:
		if not any(row):
			continue

		if row[idx["REFERENCE"]] == "" or row[idx["REFERENCE"]] is None:
			continue

		details = row[idx["REFERENCE"]].split("|")
		amount = row[idx["AMOUNT"]]
		if isinstance(amount, str):
			amount = amount.replace(",", "").replace(" KES", "").replace("Sh", "").strip()
			amount = float(amount) if amount else 0
		else:
			amount = float(amount or 0)
		data.append(
			{
				"scholar": details[1] if len(details) > 1 else None,
				"fee_request": details[0] if len(details) > 0 else None,
				"amount": amount,
			}
		)

	return data


def find_header_index(rows, expected_header, bank="Teen Mom Stipend"):
	for i, row in enumerate(rows):
		if expected_header in row:
			return i, row

	frappe.throw(
		f"Header '{expected_header}' not found. Please ensure the file attached is in the correct format for {bank}."
	)
