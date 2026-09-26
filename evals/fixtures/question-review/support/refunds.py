from typesafe_sdk import Noul, NoulCriteria, TypeSafeClient

from support.replies import offer_refund, route_to_agent

QUESTIONS = {
    "refund_request": Noul(
        instructions="Is the customer angry and asking for a refund?",
    ),
    "wants_human": Noul(
        instructions="Does the customer ask to speak with a person instead of getting an automated reply?",
        criteria=NoulCriteria(
            true="Asks for a human, an agent, a manager, or a phone call with a person",
            false="No request to talk to a person",
        ),
    ),
}


def handle(message: str) -> None:
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=message, questions=QUESTIONS).answers
    if answers["wants_human"].noul > 0.7:
        route_to_agent(message)
    elif answers["refund_request"].noul > 0.7:
        offer_refund(message)
