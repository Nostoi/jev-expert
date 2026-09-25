from types import SimpleNamespace

from ticket_router import jev_classifier
from ticket_router.models import Ticket


class FakeClient:
    def system_one(self, state, questions):
        return SimpleNamespace(
            answers={
                "queue": SimpleNamespace(choice="billing", confidence=0.97),
                "urgent": SimpleNamespace(noul=0.1),
            }
        )


def test_billing(monkeypatch):
    monkeypatch.setattr(jev_classifier, "_client", FakeClient())
    route = jev_classifier.classify(Ticket("T1", "Refund", "charged twice", "pro"))
    assert route.queue == "billing"
    assert route.urgent is False
