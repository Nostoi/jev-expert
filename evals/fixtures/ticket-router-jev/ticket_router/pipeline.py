import logging

from . import actions, jev_classifier
from .classifier import classify
from .config import load_settings
from .models import Ticket

log = logging.getLogger(__name__)


def handle_ticket(ticket: Ticket) -> None:
    settings = load_settings()
    route = classify(ticket)

    if settings.jev_mode in ("shadow", "active"):
        jev_route = jev_classifier.classify(ticket)
        if jev_route.urgent:
            actions.page_oncall(ticket, settings.pagerduty_service)
        if settings.jev_mode == "active":
            route = jev_route
        else:
            log.info("shadow: keyword=%s jev=%s", route, jev_route)

    if route.urgent:
        actions.page_oncall(ticket, settings.pagerduty_service)
    if route.queue == "billing" and settings.auto_reply_enabled:
        actions.send_auto_reply(ticket, "billing-received")
    actions.enqueue(ticket, route.queue)
