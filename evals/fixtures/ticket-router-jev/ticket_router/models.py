from dataclasses import dataclass

QUEUES = ("billing", "technical", "account", "general")


@dataclass(frozen=True)
class Ticket:
    id: str
    subject: str
    body: str
    customer_plan: str  # verified from the account system, not from the ticket text


@dataclass(frozen=True)
class Route:
    queue: str
    urgent: bool
