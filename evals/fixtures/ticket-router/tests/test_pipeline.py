import pytest

from ticket_router import actions
from ticket_router.models import Ticket
from ticket_router.pipeline import handle_ticket


@pytest.fixture(autouse=True)
def clear_outbox():
    actions.PAGES.clear()
    actions.REPLIES.clear()
    actions.QUEUED.clear()


def t(subject, body, plan="pro"):
    return Ticket(id="T1", subject=subject, body=body, customer_plan=plan)


def test_billing_ticket_gets_auto_reply():
    handle_ticket(t("Refund please", "I was charged twice"))
    assert actions.QUEUED == [("T1", "billing")]
    assert actions.REPLIES == [("T1", "billing-received")]


def test_outage_pages_oncall():
    handle_ticket(t("Everything is down", "Production outage for all users"))
    assert actions.PAGES == ["T1"]


def test_unknown_goes_general():
    handle_ticket(t("Question", "Do you have a roadmap?"))
    assert actions.QUEUED == [("T1", "general")]
    assert actions.PAGES == []
