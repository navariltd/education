from erpnext.accounts.doctype.payment_entry.payment_entry import (
    PaymentEntry as BasePaymentEntry,
)

from education.education.doctype.fee_request.fee_request import (
    update_fee_request_from_payment_entry,
)


class PaymentEntry(BasePaymentEntry):
    def on_submit(self):
        super().on_submit()
        update_fee_request_from_payment_entry(self)

    def on_cancel(self):
        super().on_cancel()
        self.ignore_linked_doctypes = (
            *self.ignore_linked_doctypes,
            "Fee Request",
        )
        update_fee_request_from_payment_entry(self)

    def on_update_after_submit(self):
        super().on_update_after_submit()
        update_fee_request_from_payment_entry(self)
