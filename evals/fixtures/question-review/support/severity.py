from typesafe_sdk import Score, TypeSafeClient

from support.alerts import page_on_call, notify_trust_and_safety

QUESTIONS = {
    "severity": Score(
        instructions="How severe is the problem the customer reports?",
        criteria=[
            "Level 1: minor",
            "Level 2: worse than level 1",
            "Level 3: worse than level 2",
            "Level 4: the worst",
        ],
    ),
    "tone": Score(
        instructions="How is the customer treating our support staff in this message?",
        criteria=[
            "Polite or neutral; no complaint about staff",
            "Frustrated: complains about the problem or the wait but stays civil",
            "Abusive: insults, threats, or slurs directed at staff",
        ],
    ),
}


def assess(ticket_text: str) -> None:
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=ticket_text, questions=QUESTIONS).answers
    if answers["severity"].score >= 2.5:
        page_on_call(ticket_text)
    if answers["tone"].score >= 1.5:
        notify_trust_and_safety(ticket_text)
