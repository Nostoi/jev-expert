from typesafe_sdk import Choice, TypeSafeClient

from support.queues import enqueue

# Every email sent to help@ comes through here: customers, vendors, job applicants, spam.
QUESTIONS = {
    "team": Choice(
        instructions="Which team should handle this email?",
        criteria={
            "billing": "Charges, invoices, refunds of payments, payment methods",
            "shipping": "Delivery status, delays, lost or stolen packages, address changes",
            "returns": "Exchanges, wrong or damaged items, return labels",
        },
    ),
}


def route(email_body: str) -> None:
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=email_body, questions=QUESTIONS).answers
    enqueue(answers["team"].choice, email_body)
