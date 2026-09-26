import json

from typesafe_sdk import Noul, TypeSafeClient

from sales.review import hold_for_manual_review, add_gift_wrap_offer

QUESTIONS = {
    "big_order": Noul(
        instructions="Is the total value of this cart above $500?",
    ),
    "gift": Noul(
        instructions="Does the customer's note say the order is a gift for someone else?",
    ),
}


def check_cart(cart: dict) -> None:
    # cart = {"items": [{"sku": ..., "unit_price": 129.0, "quantity": 3}, ...], "note": "..."}
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=json.dumps(cart), questions=QUESTIONS).answers
    if answers["big_order"].noul > 0.5:
        hold_for_manual_review(cart)
    if answers["gift"].noul > 0.6:
        add_gift_wrap_offer(cart)
