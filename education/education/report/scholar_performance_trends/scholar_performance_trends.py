# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from collections import defaultdict

from education.education.api import get_grade


def execute(filters=None):
	columns = get_columns(filters)
	data, stats = get_data(filters)
	report_summary = None
	if stats:
		report_summary = [
			{
				"value": stats["improved_pct"],
				"label": "Improved",
				"datatype": "Percent",
				"indicator": "green",
			},
			{
				"value": stats["maintained_pct"],
				"label": "Maintained",
				"datatype": "Percent",
				"indicator": "blue",
			},
			{
				"value": stats["declined_pct"],
				"label": "Declined",
				"datatype": "Percent",
				"indicator": "red",
			},
		]

	return columns, data, None, None, report_summary


def get_columns(filters):
	columns = [
		{
			"label": _("Scholar Result"),
			"fieldname": "scholar_result",
			"fieldtype": "Link",
			"options": "Scholar Result",
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
			"label": _("Official School Name"),
			"fieldname": "official_school_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Score"),
			"fieldname": "score",
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"label": _("Grade"),
			"fieldname": "grade",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Position in Class"),
			"fieldname": "position",
			"fieldtype": "Int",
			"width": 150,
		},
		{
			"label": _("Total Students in Class"),
			"fieldname": "students_in_class",
			"fieldtype": "Int",
			"width": 180,
		},
	]

	if not filters.get("show_average_performance"):
		return columns

	columns = [
		{
			"label": _("Academic Year"),
			"fieldname": "academic_year",
			"fieldtype": "Link",
			"options": "Academic Year",
			"width": 120,
		},
		{
			"label": _("Average Score"),
			"fieldname": "average_score",
			"fieldtype": "Float",
			"precision": 2,
			"width": 150,
		},
		{
			"label": _("Average Grade"),
			"fieldname": "average_grade",
			"fieldtype": "Data",
			"width": 120,
		},
	]

	if filters.get("average_by") == "Class":
		columns.insert(
			1,
			{
				"label": _("Class"),
				"fieldname": "class",
				"fieldtype": "Link",
				"options": "Class",
				"width": 150,
			},
		)

	if filters.get("average_by") == "Academic Term":
		columns.insert(
			1,
			{
				"label": _("Academic Term"),
				"fieldname": "academic_term",
				"fieldtype": "Link",
				"options": "Academic Term",
				"width": 120,
			},
		)

	return columns


def get_data(filters):
	if not filters or not filters.get("academic_year"):
		frappe.msgprint(_("Please select an Academic Year"), indicator="red")
		return [], {}

	all_results = get_scholar_results_query(filters)

	if not all_results:
		return [], {}

	# Group results by scholar
	scholar_results = defaultdict(list)
	for res in all_results:
		scholar_results[res["scholar"]].append(res)

	if not filters.get("show_average_performance"):
		return process_current_academic_year_results(filters, scholar_results)

	return process_average_performance(filters, scholar_results)


def get_scholar_results_query(filters):
	selected_academic_year = filters["academic_year"]
	class_filter = filters.get("class")

	scholar_condition = ""
	if class_filter:
		scholar_condition = f"AND sr.class = '{class_filter}'"

	if filters.get("academic_term"):
		scholar_condition += f" AND sr.academic_term = '{filters['academic_term']}'"

	if filters.get("grading_scale"):
		scholar_condition += f" AND sr.grading_scale = '{filters['grading_scale']}'"

	scholars_query = f"""
        SELECT DISTINCT sr.scholar
        FROM `tabScholar Result` sr
        WHERE sr.docstatus = 1
          AND sr.academic_year = '{selected_academic_year}'
          {scholar_condition}
    """
	scholars = frappe.db.sql(scholars_query, as_dict=True)
	if not scholars:
		return []

	scholar_list = [s["scholar"] for s in scholars]
	scholar_placeholders = ",".join(["%s"] * len(scholar_list))

	all_results_query = f"""
		SELECT
			sr.name,
			sr.scholar,
			sr.class,
			sr.academic_year,
			sr.academic_term,
			sr.posting_date,
            sr.official_school_name,

			(
				SELECT detail.position_in_class
				FROM `tabScholar Result Detail` detail
				WHERE detail.parent = sr.name
				LIMIT 1
			) AS position,

            (
				SELECT detail.total_students_in_class
				FROM `tabScholar Result Detail` detail
				WHERE detail.parent = sr.name
				LIMIT 1
			) AS students_in_class,

			(
				SELECT detail.score
				FROM `tabScholar Result Detail` detail
				WHERE detail.parent = sr.name
				LIMIT 1
			) AS score,

            (
				SELECT detail.grade
				FROM `tabScholar Result Detail` detail
				WHERE detail.parent = sr.name
				LIMIT 1
			) AS grade

		FROM `tabScholar Result` sr
		WHERE sr.docstatus = 1
		AND sr.scholar IN ({scholar_placeholders})
		ORDER BY sr.scholar, sr.posting_date DESC
	"""
	all_results = frappe.db.sql(all_results_query, tuple(scholar_list), as_dict=True)
	return all_results


def process_current_academic_year_results(filters, scholar_results):
	data = []
	stats = {
		"improved": 0,
		"maintained": 0,
		"declined": 0,
	}
	for results in scholar_results.values():
		# Process the current academic year results
		current_year_results = [
			r for r in results[:1] if r["academic_year"] == filters.get("academic_year")
		]
		if current_year_results:
			current = current_year_results[0]
			previous = results[1] if len(results) > 1 else None
			data.append(
				{
					"scholar_result": current["name"],
					"scholar": current["scholar"],
					"official_school_name": current["official_school_name"],
					"score": current["score"],
					"grade": current["grade"],
					"position": current["position"],
					"students_in_class": current["students_in_class"],
				}
			)

			if previous:
				if current["position"] < previous["position"]:
					stats["improved"] += 1
				elif current["position"] == previous["position"]:
					stats["maintained"] += 1
				else:
					stats["declined"] += 1

	stats_pct = {
		"improved_pct": round(stats["improved"] / len(data) * 100, 1) if data else 0,
		"maintained_pct": (round(stats["maintained"] / len(data) * 100, 1) if data else 0),
		"declined_pct": round(stats["declined"] / len(data) * 100, 1) if data else 0,
	}

	return data, stats_pct


def process_average_performance(filters, scholar_results):
	if filters.get("average_by") == "Class":
		class_results = defaultdict(list)
		for results in scholar_results.values():
			for res in results:
				key = (res["academic_year"], res["class"])
				class_results[key].append(res)

		if not class_results:
			return [], {}

		data = []

		for (academic_year, class_name), results in class_results.items():
			if academic_year != filters.get("academic_year"):
				continue

			avg_score = sum(r["score"] for r in results if r["score"] is not None) / len(results)
			grade_scale = filters.get("grading_scale")

			data.append(
				{
					"academic_year": academic_year,
					"class": class_name,
					"average_score": round(avg_score, 2),
					"average_grade": get_grade(grade_scale, avg_score),
				}
			)

		return data, {}

	if filters.get("average_by") == "Academic Term":
		term_results = defaultdict(list)
		for results in scholar_results.values():
			for res in results:
				key = (res["academic_year"], res["academic_term"])
				term_results[key].append(res)

		if not term_results:
			return [], {}

		data = []

		for (academic_year, academic_term), results in term_results.items():
			if academic_year != filters.get("academic_year"):
				continue

			avg_score = sum(r["score"] for r in results if r["score"] is not None) / len(results)
			grade_scale = filters.get("grading_scale")

			data.append(
				{
					"academic_year": academic_year,
					"academic_term": academic_term,
					"average_score": round(avg_score, 2),
					"average_grade": get_grade(grade_scale, avg_score),
				}
			)

		return data, {}

	if filters.get("average_by") == "Academic Year":
		year_results = defaultdict(list)
		for results in scholar_results.values():
			for res in results:
				key = res["academic_year"]
				year_results[key].append(res)

		if not year_results:
			return [], {}

		data = []

		for academic_year, results in year_results.items():
			if academic_year != filters.get("academic_year"):
				continue

			avg_score = sum(r["score"] for r in results if r["score"] is not None) / len(results)
			grade_scale = filters.get("grading_scale")

			data.append(
				{
					"academic_year": academic_year,
					"average_score": round(avg_score, 2),
					"average_grade": get_grade(grade_scale, avg_score),
				}
			)

		return data, {}

	return [], {}
