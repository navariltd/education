import frappe


def get_account_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	if "System Manager" in frappe.get_roles(user):
		return ""

	regions = frappe.get_all(
		"NL Region", filters=[["user_group", "!=", ""]], pluck="user_group"
	)
	if not regions:
		return ""

	allowed_regions = frappe.get_all(
		"User Group Member",
		filters=[["parent", "in", regions], ["user", "=", user]],
		pluck="parent",
	)

	allowed_counties = frappe.get_all(
		"Region County", filters=[["parent", "in", allowed_regions]], pluck="county"
	)

	escaped = ",".join([frappe.db.escape(val) for val in allowed_counties])

	return f"""
        (
            `tabScholar Recruitment`.county IN ({escaped}) # noqa: W604
        )
        """
