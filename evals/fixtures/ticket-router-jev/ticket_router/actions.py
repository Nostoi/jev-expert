"""All side effects. In production these call PagerDuty and the mail service."""

import logging

from .models import Ticket

log = logging.getLogger(__name__)

PAGES: list[str] = []
REPLIES: list[tuple[str, str]] = []
QUEUED: list[tuple[str, str]] = []


def page_oncall(ticket: Ticket, service: str) -> None:
    log.info("paging %s for ticket %s", service, ticket.id)
    PAGES.append(ticket.id)


def send_auto_reply(ticket: Ticket, template: str) -> None:
    log.info("auto-reply %s to ticket %s", template, ticket.id)
    REPLIES.append((ticket.id, template))


def enqueue(ticket: Ticket, queue: str) -> None:
    QUEUED.append((ticket.id, queue))
