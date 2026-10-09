"""Explicit, idempotent demo data. Existing projects and passwords are untouched."""

import asyncio
import time
import uuid

from sqlalchemy import select

from app.agreement import tokenize
from app.auth import hasher
from app.config import settings
from app.db import SessionLocal
from app.models import Annotation, Assignment, Item, Membership, Project, User

DEMO_NAMES = [
    ("admin", "Alex Morgan", "admin"),
    ("reviewer", "Jordan Lee", "reviewer"),
    ("annotator1", "Sam Rivera", "annotator"),
    ("annotator2", "Taylor Chen", "annotator"),
    ("annotator3", "Casey Park", "annotator"),
]


def stable(value):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "concord.demo/" + value))


async def seed(db):
    people = []
    password = hasher.hash(settings.demo_password)
    for login, name, role in DEMO_NAMES:
        person = await db.scalar(select(User).where(User.email == f"{login}@concord.demo"))
        if not person:
            person = User(
                id=stable(login),
                pseudonym=stable("public/" + login),
                email=f"{login}@concord.demo",
                name=name,
                role=role,
                password_hash=password,
            )
            db.add(person)
        if role == "annotator":
            people.append(person)
    await db.flush()
    specs = [
        (
            "rating",
            "Response quality",
            "Evaluate helpfulness and clarity in everyday AI conversations.",
            ["Needs work", "Acceptable", "Excellent"],
            18,
        ),
        (
            "ner",
            "Entities in the wild",
            "Find the people, places, and organizations that give text its meaning.",
            ["PERSON", "ORG", "LOCATION"],
            12,
        ),
        (
            "ab",
            "The better answer",
            "Compare two anonymous responses. Let quality decide the winner.",
            [],
            12,
        ),
    ]
    prompts = [
        "How can I make my workday more focused?",
        "Explain why leaves change color in autumn.",
        "Write a kind note to welcome a new teammate.",
        "What makes a good research question?",
        "Suggest a simple way to reduce food waste.",
        "Explain the difference between weather and climate.",
    ]
    responses = [
        "Choose one important task, silence notifications, and work in a 25-minute block. Take a short break before starting again.",
        "As daylight shortens, trees stop producing chlorophyll. Yellow and orange pigments become visible, while some leaves also produce red pigments.",
        "Welcome to the team! We’re glad you’re here. Please ask questions freely—we’re looking forward to getting to know you.",
        "A good research question is specific, answerable with evidence, and connected to a meaningful gap in what we know.",
        "Before shopping, check what you already have. Plan a meal around the ingredients that need using first.",
        "Weather describes conditions over hours or days. Climate describes long-term patterns, typically measured over decades.",
    ]
    texts = [
        "Maya Chen joined OpenAI in San Francisco.",
        "José visited the Louvre in Paris.",
        "Amina works at UNESCO in Nairobi.",
        "Dr. Kim met Luca in Taipei.",
        "Microsoft opened an office in London.",
        "Sofia and André traveled to Montréal. 🌿",
    ]
    for mode, name, description, labels, count in specs:
        project_id = stable(mode)
        if await db.get(Project, project_id):
            continue
        project = Project(
            id=project_id,
            name=name,
            description=description,
            mode=mode,
            state="active",
            labels=labels,
            ordered=mode == "rating",
            target_raters=3,
            review_threshold=0.8,
            metric_revision=18,
        )
        db.add(project)
        await db.flush()
        db.add_all([Membership(project_id=project_id, user_id=u.id) for u in people])
        for index in range(count):
            if mode == "rating":
                content = {"prompt": prompts[index % 6], "response": responses[index % 6]}
            elif mode == "ner":
                content = {"text": texts[index % 6]}
            else:
                content = {
                    "prompt": prompts[index % 6],
                    "response_a": responses[index % 6],
                    "response_b": "It depends on the situation. There are many possible approaches to consider.",
                }
            item = Item(
                id=stable(f"{mode}/{index}"),
                project_id=project_id,
                external_id=f"{mode.upper()}-{index + 1:04}",
                content=content,
                extra={"source": "Concord demo", "batch": "autumn-01"},
                tokens=tokenize(content["text"]) if mode == "ner" else [],
            )
            db.add(item)
            await db.flush()
            if index >= 6:
                continue
            for pos, person in enumerate(people):
                assignment = Assignment(
                    id=stable(f"{mode}/{index}/{pos}"),
                    project_id=project_id,
                    item_id=item.id,
                    user_id=person.id,
                    expires_at=0,
                    version=1,
                    swapped=bool(pos % 2),
                )
                db.add(assignment)
                await db.flush()
                if mode == "rating":
                    payload = {
                        "label": labels[1 if index == 2 and pos == 2 else index % 3],
                        "note": "",
                    }
                elif mode == "ab":
                    payload = {
                        "choice": "B" if index == 2 and pos == 2 else "TIE" if index == 4 else "A",
                        "note": "",
                    }
                else:
                    token = item.tokens[0]
                    payload = {
                        "spans": []
                        if index == 2 and pos == 2
                        else [{**token, "label": "ORG" if index == 4 else "PERSON"}]
                    }
                db.add(
                    Annotation(
                        assignment_id=assignment.id,
                        project_id=project_id,
                        item_id=item.id,
                        user_id=person.id,
                        payload=payload,
                        status="submitted",
                        submitted_at=time.time() - 86400 + index * 60 + pos,
                    )
                )
    await db.commit()


async def main():
    async with SessionLocal() as db:
        await seed(db)
    print("Demo ready: admin, reviewer, annotator1, annotator2, annotator3 @concord.demo")


if __name__ == "__main__":
    asyncio.run(main())
