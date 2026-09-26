from typesafe_sdk import Noul, TypeSafeClient

QUESTIONS = {
    "python_skill": Noul(
        instructions="Is the candidate strong in Python?",
    ),
}


def python_level(resume_text: str) -> str:
    with TypeSafeClient() as client:
        answers = client.system_one(model="jev-1.13.0", state=resume_text, questions=QUESTIONS).answers
    value = answers["python_skill"].noul
    if value > 0.66:
        return "senior"
    if value > 0.33:
        return "mid"
    return "junior"
