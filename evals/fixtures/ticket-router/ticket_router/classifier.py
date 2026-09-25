"""Keyword classifier. Brittle: misroutes paraphrases and mixed tickets."""

from .models import Route, Ticket

_KEYWORDS = {
    "billing": ("invoice", "refund", "charge", "billing", "payment"),
    "technical": ("error", "crash", "bug", "not working", "broken", "500"),
    "account": ("password", "login", "sso", "2fa", "locked out"),
}
_URGENT = ("outage", "down", "urgent", "asap", "all users", "production")


def classify(ticket: Ticket) -> Route:
    text = f"{ticket.subject} {ticket.body}".lower()
    queue = "general"
    for name, words in _KEYWORDS.items():
        if any(w in text for w in words):
            queue = name
            break
    urgent = any(w in text for w in _URGENT)
    return Route(queue=queue, urgent=urgent)
