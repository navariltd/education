// Prompts for a single comment before a bulk workflow transition in the list view, and
// applies it to every selected document. Active for any doctype with an active workflow.
//
// Frappe already adds one Actions menu entry per workflow transition and keeps a
// reference to each in `listview.workflow_action_items` so they can be shown or hidden.
// We reuse those entries and only replace their click handler, so no core method is
// overridden and Frappe keeps managing which transitions are offered for a selection.

const BOUND_FLAG = 'education-bulk-comment-bound'

const REQUIREMENT_METHOD =
  'education.education.workflow.get_comment_requirement'
const TRANSITION_METHOD = 'education.education.workflow.bulk_transition'

$(document).on('show.bs.dropdown', '.actions-btn-group', (event) => {
  const listview = window.cur_list

  if (!listview || !listview.page || !listview.doctype) return
  if (!listview.page.actions_btn_group.is(event.currentTarget)) return
  if (!frappe.model.has_workflow(listview.doctype)) return

  claim_workflow_actions(listview)
})

function claim_workflow_actions(listview) {
  // Frappe reuses an existing menu entry when the labels match, so a workflow action
  // named after a bulk operation ('Cancel', 'Submit') shares that entry rather than
  // getting its own. Leave those alone instead of changing what the bulk operation does.
  const bulk_labels = new Set(
    (listview.actions_menu_items || []).map((item) => item.label)
  )

  Object.entries(listview.workflow_action_items || {}).forEach(
    ([action, $link]) => {
      if (!$link || $link.data(BOUND_FLAG)) return

      if (bulk_labels.has(__(action))) {
        console.warn(
          `[education] Workflow action '${action}' on ${listview.doctype} shares a label with a bulk action, so the comment prompt was not applied to it.`
        )
        return
      }

      $link
        .data(BOUND_FLAG, true)
        .off('click')
        .on('click', () => {
          collect_comment(listview, action)
          return false
        })
    }
  )
}

async function collect_comment(listview, action) {
  const docs = listview.get_checked_items()
  if (!docs.length) return

  const state_field = frappe.workflow.get_state_fieldname(listview.doctype)
  const states = Array.from(
    new Set(docs.map((doc) => doc[state_field]).filter(Boolean))
  )

  const requirement = await frappe.xcall(REQUIREMENT_METHOD, {
    doctype: listview.doctype,
    action: action,
    states: states,
  })

  if (!requirement.requires_comment) {
    apply(listview, action, docs, null)
    return
  }

  const dialog = new frappe.ui.Dialog({
    title: __('Comment Required'),
    fields: [
      {
        fieldname: 'comment',
        fieldtype: 'Small Text',
        label: __('Comment'),
        reqd: 1,
        description: __('Added to all {0} selected document(s).', [
          docs.length,
        ]),
      },
    ],
    primary_action_label: __('Continue'),
    primary_action: ({ comment }) => {
      dialog.hide()
      apply(listview, action, docs, comment)
    },
  })

  dialog.show()
}

async function apply(listview, action, docs, comment) {
  listview.disable_list_update = true

  try {
    await frappe.xcall(TRANSITION_METHOD, {
      doctype: listview.doctype,
      docnames: docs.map((doc) => doc.name),
      action: action,
      comment: comment,
    })
  } finally {
    listview.disable_list_update = false
    listview.clear_checked_items()
    listview.refresh()
  }
}
