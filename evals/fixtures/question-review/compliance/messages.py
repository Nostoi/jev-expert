from typesafe_sdk import Noul, NoulCriteria, TypeSafeClient

from compliance.actions import redact_and_hold, page_incident_channel

QUESTIONS = {
    "pii_ok": Noul(
        instructions="Is the message free of personal data?",
    ),
    "outage": Noul(
        instructions="Does this message describe an urgent problem?",
        criteria=NoulCriteria(
            true="Reports a production outage, or data loss or corruption, happening now",
            false="Anything else, including slowness, feature requests, and questions",
        ),
    ),
}


def screen(message: str) -> None:
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=message, questions=QUESTIONS).answers
    if answers["pii_ok"].noul < 0.5:
        redact_and_hold(message)
    if answers["outage"].noul > 0.8:
        page_incident_channel(message)
