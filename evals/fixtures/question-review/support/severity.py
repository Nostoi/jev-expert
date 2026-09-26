from typesafe_sdk import Score, TypeSafeClient

from support.alerts import page_on_call

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
}


def assess(ticket_text: str) -> None:
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=ticket_text, questions=QUESTIONS).answers
    if answers["severity"].score >= 2.5:
        page_on_call(ticket_text)
