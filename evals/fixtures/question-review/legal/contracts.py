from typesafe_sdk import Noul, TypeSafeClient

from legal.pricing import apply_quoted_price, requote

QUESTIONS = {
    "signed_in_window": Noul(
        instructions="Was the contract signed within 30 days of the quote date?",
    ),
}


def price_contract(contract_text: str) -> None:
    # contract_text includes the quote date and the signature date, in whatever format the customer used.
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=contract_text, questions=QUESTIONS).answers
    if answers["signed_in_window"].noul > 0.5:
        apply_quoted_price(contract_text)
    else:
        requote(contract_text)
