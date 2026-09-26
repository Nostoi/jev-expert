from typesafe_sdk import Noul, NoulCriteria, TypeSafeClient

from support.tiers import send_to_tier2

QUESTIONS = {
    "escalate": Noul(
        instructions="Does this ticket need to be escalated to tier 2?",
        criteria=NoulCriteria(
            true="Tier 1 can resolve it with the standard playbook",
            false="It needs an engineer, or a refund above the tier 1 limit",
        ),
    ),
}


def maybe_escalate(ticket_text: str) -> None:
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=ticket_text, questions=QUESTIONS).answers
    if answers["escalate"].noul > 0.6:
        send_to_tier2(ticket_text)
