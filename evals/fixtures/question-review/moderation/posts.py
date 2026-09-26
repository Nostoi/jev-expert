from typesafe_sdk import Choice, Noul, TypeSafeClient

from moderation.queue import flag_for_marketing, tag_post

QUESTIONS = {
    "mentions_competitor": Noul(
        instructions="Does this apply?",
    ),
    "topic": Choice(
        instructions="What is the main topic of this community forum post?",
        criteria={
            "how_to": "Asks how to do something with the product",
            "bug_report": "Reports that something in the product is broken",
            "feature_request": "Asks for something the product does not do yet",
            "showcase": "Shares something the author built or achieved with the product",
            "other": "A post that fits none of the topics above",
        },
    ),
}


def review_post(post_text: str) -> None:
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=post_text, questions=QUESTIONS).answers
    if answers["mentions_competitor"].noul > 0.7:
        flag_for_marketing(post_text)
    tag_post(post_text, answers["topic"].choice)
