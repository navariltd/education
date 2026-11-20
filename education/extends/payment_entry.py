from erpnext.accounts.doctype.payment_entry.payment_entry import (
    PaymentEntry as BasePaymentEntry,
)

from education.education.doctype.fee_request.fee_request import ignore_fee_request_links


class PaymentEntry(BasePaymentEntry):
    # Fee Request balances follow the Payment Ledger through doc_events in hooks.py.
    def on_cancel(self):
        super().on_cancel()
        ignore_fee_request_links(self)
