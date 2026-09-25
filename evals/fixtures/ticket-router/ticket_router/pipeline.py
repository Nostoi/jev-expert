from . import actions
from .classifier import classify
from .config import load_settings
from .models import Ticket


def handle_ticket(ticket: Ticket) -> None:
    settings = load_settings()
    route = classify(ticket)
    if route.urgent:
        actions.page_oncall(ticket, settings.pagerduty_service)
    if route.queue == "billing" and settings.auto_reply_enabled:
        actions.send_auto_reply(ticket, "billing-received")
    actions.enqueue(ticket, route.queue)
