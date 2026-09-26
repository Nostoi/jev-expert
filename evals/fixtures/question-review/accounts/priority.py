from typesafe_sdk import Noul, TypeSafeClient

from accounts.sla import apply_priority_sla

QUESTIONS = {
    "enterprise": Noul(
        instructions="Is this customer on the Enterprise plan?",
    ),
}


def set_sla(ticket: dict) -> None:
    # ticket = {"subject": "...", "body": "..."} exactly as the customer submitted it.
    state = f"Subject: {ticket['subject']}\n\n{ticket['body']}"
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=state, questions=QUESTIONS).answers
    if answers["enterprise"].noul > 0.5:
        apply_priority_sla(ticket)
