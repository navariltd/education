import frappe
from frappe import _
from frappe.model.workflow import apply_workflow

REQUIRE_COMMENT_FIELD = "custom_require_comment"

INLINE_LIMIT = 20
MAX_BULK_DOCUMENTS = 500

DOCSTATUS_STYLES = {
    0: {"bg": "#fff3cd", "border": "#ffc107", "text": "#856404", "icon": "⊙"},
    1: {"bg": "#e8f5e9", "border": "#4caf50", "text": "#2e7d32", "icon": "✓"},
    2: {"bg": "#ffebee", "border": "#f44336", "text": "#c62828", "icon": "✕"},
}


def get_active_workflow(doctype: str) -> str | None:
    return frappe.db.get_value(
        "Workflow", {"document_type": doctype, "is_active": 1}, "name"
    )


def has_require_comment_field() -> bool:
    return frappe.get_meta("Workflow Transition").has_field(REQUIRE_COMMENT_FIELD)


def get_transition(workflow: str, state: str, action: str) -> frappe._dict | None:
    fields = ["next_state"]
    if has_require_comment_field():
        fields.append(REQUIRE_COMMENT_FIELD)

    rows = frappe.get_all(
        "Workflow Transition",
        filters={"parent": workflow, "state": state, "action": action},
        fields=fields,
        limit=1,
    )
    return rows[0] if rows else None


@frappe.whitelist()
def get_comment_requirement(doctype: str, action: str, states=None) -> dict:
    """Return whether applying `action` to documents in `states` requires a comment.

    `states` is the set of workflow states the selected documents are currently in. When
    it cannot be resolved by the caller, every transition for `action` is considered, so
    that the prompt is never skipped silently.
    """
    workflow = get_active_workflow(doctype)
    if not workflow or not has_require_comment_field():
        return {"workflow": workflow, "requires_comment": False}

    filters = {"parent": workflow, "action": action, REQUIRE_COMMENT_FIELD: 1}

    states = [state for state in (frappe.parse_json(states) or []) if state]
    if states:
        filters["state"] = ["in", states]

    return {
        "workflow": workflow,
        "requires_comment": bool(frappe.db.exists("Workflow Transition", filters)),
    }


@frappe.whitelist()
def bulk_transition(
    doctype: str, docnames, action: str, comment: str | None = None
) -> dict | None:
    """Apply a workflow action to many documents, commenting on each one that succeeds."""
    frappe.has_permission(doctype, "write", throw=True)

    docnames = frappe.parse_json(docnames) or []
    if not docnames:
        return

    workflow = get_active_workflow(doctype)
    if not workflow:
        frappe.throw(_("{0} does not have an active workflow.").format(_(doctype)))

    if len(docnames) > MAX_BULK_DOCUMENTS:
        frappe.throw(
            _("Bulk workflow actions are limited to {0} documents at a time.").format(
                MAX_BULK_DOCUMENTS
            ),
            title=_("Too Many Documents"),
        )

    if len(docnames) <= INLINE_LIMIT:
        return apply_to_many(docnames, doctype, workflow, action, comment)

    frappe.msgprint(
        _("Bulk {0} has been queued in the background.").format(action), alert=True
    )
    frappe.enqueue(
        apply_to_many,
        docnames=docnames,
        doctype=doctype,
        workflow=workflow,
        action=action,
        comment=comment,
        queue="short",
        timeout=1000,
    )


def apply_to_many(
    docnames: list[str],
    doctype: str,
    workflow: str,
    action: str,
    comment: str | None = None,
) -> dict:
    state_field = frappe.db.get_value("Workflow", workflow, "workflow_state_field")

    succeeded = []
    failed = {}
    total = len(docnames)

    for idx, docname in enumerate(docnames, 1):
        if total >= 5:
            frappe.publish_progress(
                idx * 100 / total,
                title=_("Applying: {0}").format(action),
                description=docname,
            )

        try:
            apply_to_one(doctype, docname, workflow, state_field, action, comment)
            frappe.db.commit()
            succeeded.append(docname)
        except Exception as exc:
            frappe.db.rollback()
            failed[docname] = str(exc) or exc.__class__.__name__
            frappe.clear_messages()
            frappe.log_error(
                title=f"Bulk workflow {action} failed for {doctype} {docname}",
                reference_doctype="Workflow",
                reference_name=workflow,
            )

    notify_result(doctype, action, succeeded, failed)

    return {"succeeded": succeeded, "failed": failed}


def apply_to_one(
    doctype: str,
    docname: str,
    workflow: str,
    state_field: str,
    action: str,
    comment: str | None = None,
) -> None:
    doc = frappe.get_doc(doctype, docname)
    transition = get_transition(workflow, doc.get(state_field), action)

    if not transition:
        frappe.throw(
            _("{0} is not allowed from {1}.").format(_(action), _(doc.get(state_field)))
        )

    if transition.get(REQUIRE_COMMENT_FIELD) and not (comment or "").strip():
        frappe.throw(_("A comment is required to {0} this document.").format(_(action)))

    # apply_workflow validates the transition and the user's role, and returns nothing
    # when the doctype submits in the background
    doc = apply_workflow(doc, action) or frappe.get_doc(doctype, docname)

    add_workflow_comment(doc, transition.next_state, comment)


def add_workflow_comment(doc, next_state: str, comment: str | None = None) -> None:
    if not comment:
        return

    style = DOCSTATUS_STYLES.get(int(doc.docstatus), DOCSTATUS_STYLES[0])

    content = (
        f"<div style='padding: 8px; background-color: {style['bg']}; "
        f"border-left: 4px solid {style['border']}; border-radius: 4px;'>"
        f"<strong style='color: {style['text']}'>{style['icon']} {_('Moved to')}</strong> "
        f"<span style='color: #1565c0; font-weight: bold;'>{_(next_state)}</span></div>"
    )

    if comment:
        content += (
            "<div style='margin-top: 8px; padding: 8px; background-color: #e3f2fd; "
            "border-left: 4px solid #2196f3; border-radius: 4px;'>"
            f"<strong style='color: #1565c0;'>💬 {_('Note')}:</strong> "
            f"<em style='color: #666;'>{comment}</em></div>"
        )

    doc.add_comment("Workflow", content)


def notify_result(
    doctype: str, action: str, succeeded: list[str], failed: dict
) -> None:
    if not succeeded and not failed:
        return

    if succeeded and failed:
        indicator = "orange"
    elif failed:
        indicator = "red"
    else:
        indicator = "green"

    message = ""

    if succeeded:
        applied = _("{0} applied to {1} document(s)").format(_(action), len(succeeded))
        message += f"<h5>{applied}</h5>"

    if failed:
        message += f"<h5>{_('Failed')}</h5>"
        for docname, reason in failed.items():
            link = frappe.utils.get_link_to_form(doctype, docname)
            message += f"<div class='small text-muted' style='padding:2.5px'>{link}: {reason}</div>"

    frappe.msgprint(
        message,
        title=_("Workflow Status"),
        indicator=indicator,
        is_minimizable=True,
        realtime=True,
    )
