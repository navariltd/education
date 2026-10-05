import frappe
from frappe.utils import cint


def get_user_county_filter(user=None):
    """Escaped county names for a list filter, or None when every record is visible.

    None means the caller must not add a condition. "1=0" means this user has
    no allowed counties, so the list is empty.
    """
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user):
        return None

    restricted = frappe.db.get_single_value(
        "Education Settings", "restrict_records_by_county"
    )
    if restricted is None:
        restricted = 1
    if not cint(restricted):
        return None

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
