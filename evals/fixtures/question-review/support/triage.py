from typesafe_sdk import Choice, Noul, TypeSafeClient

from support.bugs import file_bug

BUG_QUESTIONS = {
    "is_bug": Noul(
        instructions="Does the customer report something in the product not working as expected?",
    ),
}

AREA_QUESTIONS = {
    "product_area": Choice(
        instructions="Which part of the product is the customer writing about?",
        criteria={
            "editor": "Writing, formatting, or saving documents",
            "sharing": "Invites, permissions, links, and collaborators",
            "billing": "Plans, invoices, and payment",
            "other": "Any part of the product not listed above",
        },
    ),
}


def triage(ticket_text: str) -> None:
    with TypeSafeClient() as client:
        bug = client.system_one(model="jev-1.13.0", state=ticket_text, questions=BUG_QUESTIONS).answers
        if bug["is_bug"].noul > 0.6:
            area = client.system_one(model="jev-1.13.0", state=ticket_text, questions=AREA_QUESTIONS).answers
            file_bug(ticket_text, area["product_area"].choice)
