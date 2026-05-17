import frappe


def get_user_county_filter(user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user):
        return "1=0"

    user_groups = frappe.get_all(
        "NL Region", filters=[["user_group", "!=", ""]], pluck="user_group"
    )
    if not user_groups:
        return "1=0"

    allowed_user_groups = frappe.get_all(
        "User Group Member",
        filters=[["parent", "in", user_groups], ["user", "=", user]],
        pluck="parent",
    )

    if not allowed_user_groups:
        return "1=0"

    allowed_regions = frappe.get_all(
        "NL Region", filters=[["user_group", "in", allowed_user_groups]], pluck="name"
    )

    if not allowed_regions:
        return "1=0"

    allowed_counties = frappe.get_all(
        "Region County",
        filters=[["parent", "in", allowed_regions]],
        pluck="county",
    )

    if not allowed_counties:
        return "1=0"

    escaped = ",".join([frappe.db.escape(val) for val in allowed_counties])

    return escaped
