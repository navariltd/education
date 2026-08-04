from education.permissions.utils import get_user_county_filter


def get_county_query_conditions(user=None):
    allowed_counties = get_user_county_filter(user)

    return f"""
        (
            `tabCase Management`.county IN ({allowed_counties})
        )
        """
