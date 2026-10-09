import time

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agreement import calculate, validate_spans
from app.models import Adjudication, Annotation, Assignment, Item, Membership, Project, User

LEASE_SECONDS = 15 * 60


async def project_access(db: AsyncSession, project_id: str, user: User) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if user.role == "annotator" and not await db.get(Membership, (project_id, user.id)):
        raise HTTPException(403, "You are not a member of this project")
    return project


async def lock_project(db: AsyncSession, project_id: str) -> Project:
    # A real UPDATE obtains a row lock on PostgreSQL and a writer lock on SQLite.
    # Every project mutation acquires this lock before inspecting shared state.
    await db.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(queue_serial=Project.queue_serial + 1)
    )
    project = await db.get(Project, project_id, populate_existing=True)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


async def project_out(db: AsyncSession, project: Project, user: User) -> dict:
    item_count = await db.scalar(
        select(func.count()).select_from(Item).where(Item.project_id == project.id)
    )
    submission_count = await db.scalar(
        select(func.count())
        .select_from(Annotation)
        .where(Annotation.project_id == project.id, Annotation.status == "submitted")
    )
    my_count = await db.scalar(
        select(func.count())
        .select_from(Annotation)
        .where(
            Annotation.project_id == project.id,
            Annotation.status == "submitted",
            Annotation.user_id == user.id,
        )
    )
    member_count = await db.scalar(
        select(func.count()).select_from(Membership).where(Membership.project_id == project.id)
    )
    return {
        k: getattr(project, k)
        for k in [
            "id",
            "name",
            "description",
            "mode",
            "state",
            "labels",
            "ordered",
            "target_raters",
            "review_threshold",
            "metric_revision",
        ]
    } | {
        "item_count": item_count,
        "submission_count": submission_count if user.role != "annotator" else my_count,
        "my_submission_count": my_count,
        "member_count": member_count,
    }


def canonical_payload(
    project: Project, item: Item, mode: str, payload: dict, swapped=False
) -> dict:
    if mode != project.mode:
        raise HTTPException(422, "Payload mode does not match project")
    if mode == "rating" and payload["label"] not in project.labels:
        raise HTTPException(422, "Choose a configured rating label")
    if mode == "ner":
        try:
            validate_spans(item.content["text"], item.tokens, payload["spans"], project.labels)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        payload["spans"] = sorted(
            payload["spans"], key=lambda x: (x["start"], x["end"], x["label"])
        )
    if mode == "ab" and swapped:
        payload["choice"] = {"A": "B", "B": "A", "TIE": "TIE"}[payload["choice"]]
    return payload


async def assignment_out(db: AsyncSession, assignment: Assignment, project: Project) -> dict:
    item = await db.get(Item, assignment.item_id)
    content = dict(item.content)
    ann = await db.scalar(select(Annotation).where(Annotation.assignment_id == assignment.id))
    draft = dict(ann.payload) if ann else None
    if project.mode == "ab" and assignment.swapped:
        content["response_a"], content["response_b"] = content["response_b"], content["response_a"]
        if draft:
            draft["choice"] = {"A": "B", "B": "A", "TIE": "TIE"}[draft["choice"]]
    # Metadata is deliberately absent from annotator responses: it may identify
    # a model or contain gold labels, defeating blinding.
    return {
        "id": assignment.id,
        "project_id": project.id,
        "version": assignment.version,
        "expires_at": assignment.expires_at,
        "item": {
            "id": item.id,
            "external_id": item.external_id,
            "content": content,
            "tokens": item.tokens,
        },
        "draft": draft,
    }


async def active_assignment(db, project_id, user_id):
    return await db.scalar(
        select(Assignment)
        .where(
            Assignment.project_id == project_id,
            Assignment.user_id == user_id,
            Assignment.skipped.is_(False),
            Assignment.expires_at > time.time(),
            ~Assignment.id.in_(
                select(Annotation.assignment_id).where(Annotation.status == "submitted")
            ),
        )
        .order_by(Assignment.id)
    )


async def metric_data(db, project):
    items = list(
        (
            await db.scalars(
                select(Item).where(Item.project_id == project.id).order_by(Item.external_id)
            )
        ).all()
    )
    annotations = list(
        (
            await db.scalars(
                select(Annotation)
                .where(Annotation.project_id == project.id, Annotation.status == "submitted")
                .order_by(Annotation.item_id, Annotation.user_id)
            )
        ).all()
    )
    decisions = list(
        (await db.scalars(select(Adjudication).where(Adjudication.project_id == project.id))).all()
    )
    users = list((await db.scalars(select(User))).all())
    return items, annotations, decisions, users


async def metrics(db, project):
    return calculate(project, *(await metric_data(db, project)))
