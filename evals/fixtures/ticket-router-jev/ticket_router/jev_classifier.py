"""Jev-based classifier (added in v0.4)."""

import logging
import time

from typesafe_sdk import Choice, Noul, TypeSafeClient

from .models import Route, Ticket

log = logging.getLogger(__name__)

_client = None


def _get_client() -> TypeSafeClient:
    global _client
    if _client is None:
        _client = TypeSafeClient(model="jev-latest")
    return _client


def classify(ticket: Ticket) -> Route:
    state = {"subject": ticket.subject, "body": ticket.body}
    questions = {
        "queue": Choice(
            instructions="Which team should handle this support ticket?",
            criteria={
                "billing": "Invoices, refunds, charges, payment methods.",
                "technical": "Errors, crashes, bugs, features not working.",
                "account": "Login, password, SSO, 2FA, account access.",
            },
        ),
        "urgent": Noul(
            instructions="Is this an urgent production-impacting issue?",
        ),
    }
    try:
        resp = None
        for attempt in range(3):
            try:
                resp = _get_client().system_one(state=state, questions=questions)
                break
            except Exception:
                time.sleep(2**attempt)
        queue = resp.answers["queue"]
        urgent = resp.answers["urgent"]
        if queue.confidence < 0.9:
            return Route(queue="general", urgent=urgent.noul > 0.85)
        return Route(queue=queue.choice, urgent=urgent.noul > 0.85)
    except Exception:
        log.warning("jev classify failed for %s", ticket.id)
        return Route(queue="general", urgent=False)
