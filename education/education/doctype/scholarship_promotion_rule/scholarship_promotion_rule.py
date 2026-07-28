# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_year_ending, get_year_start, getdate, today


class ScholarshipPromotionRule(Document):
    def before_save(self):
        for idx, row in enumerate(self.status_progression):
            if row.current_status == row.final_status:
                frappe.throw(
                    f"Final Status '{row.final_status}' cannot be same as '{row.current_status}' in Status Progression (Row {idx+1})."
                )

        eligible_classes = set()
        for idx, row in enumerate(self.eligible_classes):
            class_name = row.get("class")
            if class_name in eligible_classes:
                frappe.throw(
                    f"Class '{class_name}' appears more than once in Eligible Classes (Row {idx + 1})."
                )
            eligible_classes.add(class_name)

        for idx, row in enumerate(self.class_progression):
            if row.current_class not in eligible_classes:
                frappe.throw(
                    f"Class '{row.current_class}' in Class Progression (Row {idx + 1}) must be included in Eligible Classes."
                )
            if row.next_class and row.next_class not in eligible_classes:
                frappe.throw(
                    f"Next Class '{row.next_class}' in Class Progression (Row {idx + 1}) must be included in Eligible Classes."
                )

        if len([d.is_final for d in self.class_progression if d.is_final]) > 1:
            frappe.throw("Only one Class Progression can be marked as Final.")

        if not any(d.is_final for d in self.class_progression):
            frappe.throw("At least one Class Progression must be marked as Final.")

    def promote_scholars(self):
        """Promote all eligible scholars based on the promotion rule"""

        eligible_statuses = [row.current_status for row in self.status_progression]

        # Build progression map
        status_progression_map = {
            row.current_status: row.final_status for row in self.status_progression
        }
        class_progression_map = {}

        final_classes = []
        for progression in self.class_progression:
            if progression.is_final:
                final_classes.append(progression.current_class)
            else:
                class_progression_map[progression.current_class] = (
                    progression.next_class
                )

        scholars = frappe.get_all(
            "Scholar",
            filters={
                "promotion_rule": self.name,
                "status": ["in", eligible_statuses],
            },
            fields=["name", "student_name", "current_class", "status"],
        )
        for scholar in scholars:
            try:
                # Check if scholar is in final class
                if scholar.current_class in final_classes:
                    # Convert to alumni
                    self.convert_to_alumni(
                        scholar.name,
                        scholar.current_class,
                        scholar.status,
                        status_progression_map.get(scholar.status, scholar.status),
                    )

                # Check if promotion is defined
                elif scholar.current_class in class_progression_map:
                    next_class = class_progression_map[scholar.current_class]
                    self.promote_scholar(
                        scholar.name,
                        scholar.current_class,
                        next_class,
                        scholar.status,
                    )

            except Exception as e:
                frappe.log_error(
                    "Scholarship Promotion Rule",
                    f"Promotion Error for {scholar.name}: {e}",
                )

    def promote_scholar(self, scholar_id, from_class, next_class, current_status):
        scholar = frappe.get_doc("Scholar", scholar_id)

        # Create progression log
        self.create_progression_log(
            scholar_id,
            scholar.student_name,
            from_class,
            next_class,
            "Automatic",
            current_status,
        )

        scholar.current_class = next_class
        scholar.save(ignore_permissions=True)

    def convert_to_alumni(self, scholar_id, from_class, current_status, final_status):
        scholar = frappe.get_doc("Scholar", scholar_id)

        # Create progression log
        self.create_progression_log(
            scholar_id,
            scholar.student_name,
            from_class,
            final_status,
            "Converted to Alumni",
            current_status,
            final=True,
        )

        scholar.status = final_status
        scholar.save(ignore_permissions=True)

        # TODO: Optionally create Alumni record

    def create_progression_log(
        self,
        scholar_id,
        student_name,
        from_class,
        to_class,
        promotion_type,
        status,
        final=False,
    ):
        log = frappe.get_doc(
            {
                "doctype": "Scholar Progression Log",
                "scholar": scholar_id,
                "student_name": student_name,
                "promotion_rule": self.name,
                "from_class": from_class,
                "to_class": to_class if not final else None,
                "promotion_type": promotion_type,
                "promotion_date": today(),
                "status": status,
            }
        )

        log.save(ignore_permissions=True)
        log.submit()
        frappe.db.commit()

        return log.name


def auto_promote_scholars_yearly():
    frappe.log_error("Starting yearly promotion process", "Promotion Rule Processing")
    promotion_rules = frappe.get_all(
        "Scholarship Promotion Rule",
        fields=["name"],
    )

    for rule in promotion_rules:
        rule_doc = frappe.get_doc("Scholarship Promotion Rule", rule.name)
        frappe.log_error(rule_doc.name, "Promotion Rule Processing")
        rule_doc.promote_scholars()
