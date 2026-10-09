import asyncio
import json
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from app.auth import current_user, digest, roles
from app.db import SessionLocal, get_db
from app.exports import export_artifact
from app.imports import MAX_BYTES, parse_import
from app.models import (
    Adjudication,
    Annotation,
    Assignment,
    Item,
    Membership,
    Project,
    Session,
    User,
)
from app.schemas import (
    AnnotationWrite,
    AssignmentOut,
    DecisionWrite,
    ImportResult,
    Members,
    Message,
    MetricsOut,
    ProjectConfig,
    ProjectOut,
    ReviewItem,
    SaveOut,
    StateChange,
    UserOut,
)
from app.service import (
    LEASE_SECONDS,
    active_assignment,
    assignment_out,
    canonical_payload,
    lock_project,
    metric_data,
    metrics,
    project_access,
    project_out,
)

router = APIRouter()
reviewer = roles("reviewer", "admin")
admin = roles("admin")
annotator = roles("annotator")


@router.get("/users", response_model=list[UserOut], tags=["Projects"])
async def list_users(
    user: User = Depends(admin), db: AsyncSession = Depends(get_db, scope="function")
):
    return (await db.scalars(select(User).order_by(User.name))).all()


@router.get("/projects", response_model=list[ProjectOut], tags=["Projects"])
async def list_projects(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db, scope="function")
):
    query = select(Project).order_by(Project.created_at, Project.id)
    if user.role == "annotator":
        query = query.join(Membership).where(Membership.user_id == user.id)
    return [await project_out(db, p, user) for p in (await db.scalars(query)).all()]


def check_config(body):
    if body.mode != "ab" and not body.labels:
        raise HTTPException(422, "Configure at least one label or entity type")
    if body.mode == "ab" and body.labels:
        raise HTTPException(422, "A/B projects use the fixed A, B and TIE choices")


@router.post("/projects", response_model=ProjectOut, status_code=201, tags=["Projects"])
async def create_project(
    body: ProjectConfig,
    user: User = Depends(admin),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    check_config(body)
    project = Project(**body.model_dump())
    db.add(project)
    await db.flush()
    return await project_out(db, project, user)


@router.get("/projects/{project_id}", response_model=ProjectOut, tags=["Projects"])
async def get_project(
    project_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await project_out(db, await project_access(db, project_id, user), user)


@router.put("/projects/{project_id}", response_model=ProjectOut, tags=["Projects"])
async def configure_project(
    project_id: str,
    body: ProjectConfig,
    user: User = Depends(admin),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    project = await lock_project(db, project_id)
    if project.state != "draft":
        raise HTTPException(409, "Configuration is locked after activation")
    check_config(body)
    if project.mode != body.mode and await db.scalar(
        select(Item.id).where(Item.project_id == project_id).limit(1)
    ):
        raise HTTPException(409, "Cannot change mode after importing items")
    for key, value in body.model_dump().items():
        setattr(project, key, value)
    await db.flush()
    return await project_out(db, project, user)


@router.get("/projects/{project_id}/members", response_model=list[UserOut], tags=["Projects"])
async def get_members(
    project_id: str,
    user: User = Depends(admin),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    await project_access(db, project_id, user)
    return (
        await db.scalars(
            select(User)
            .join(Membership)
            .where(Membership.project_id == project_id)
            .order_by(User.name)
        )
    ).all()


@router.put("/projects/{project_id}/members", response_model=Message, tags=["Projects"])
async def set_members(
    project_id: str,
    body: Members,
    user: User = Depends(admin),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    project = await lock_project(db, project_id)
    if project.state not in {"draft", "active"}:
        raise HTTPException(409, "Membership is locked for closed projects")
    people = (
        await db.scalars(
            select(User).where(User.id.in_(set(body.user_ids)), User.role == "annotator")
        )
    ).all()
    if len(people) != len(set(body.user_ids)):
        raise HTTPException(422, "Every member must be a known annotator")
    if project.state == "active" and len(people) < project.target_raters:
        raise HTTPException(422, "Keep at least the target number of annotators")
    await db.execute(delete(Membership).where(Membership.project_id == project_id))
    db.add_all([Membership(project_id=project_id, user_id=p.id) for p in people])
    # Removed members lose their claims immediately; their submitted work remains.
    for assignment in (
        await db.scalars(
            select(Assignment).where(
                Assignment.project_id == project_id, ~Assignment.user_id.in_(body.user_ids)
            )
        )
    ).all():
        assignment.expires_at = 0
    return {"message": "Membership updated"}


@router.post("/projects/{project_id}/state", response_model=ProjectOut, tags=["Projects"])
async def change_state(
    project_id: str,
    body: StateChange,
    user: User = Depends(admin),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    project = await lock_project(db, project_id)
    transitions = {
        "draft": {"active", "archived"},
        "active": {"completed", "archived"},
        "completed": {"archived"},
        "archived": set(),
    }
    if body.state not in transitions[project.state]:
        raise HTTPException(409, "Invalid project state transition")
    details = await project_out(db, project, user)
    if body.state == "active" and (
        details["item_count"] == 0 or details["member_count"] < project.target_raters
    ):
        raise HTTPException(
            422, "Import items and add at least the target number of annotators before activation"
        )
    if (
        body.state == "completed"
        and details["submission_count"] != details["item_count"] * project.target_raters
    ):
        raise HTTPException(409, "All items must reach their target before completion")
    project.state = body.state
    project.metric_revision += 1
    await db.flush()
    return await project_out(db, project, user)


@router.post("/projects/{project_id}/imports", response_model=ImportResult, tags=["Projects"])
async def import_items(
    project_id: str,
    file: UploadFile = File(...),
    user: User = Depends(admin),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Import limit is 10 MiB")
    project = await lock_project(db, project_id)
    if project.state != "draft":
        raise HTTPException(409, "Imports are available only in draft projects")
    existing = set(
        (await db.scalars(select(Item.external_id).where(Item.project_id == project_id))).all()
    )
    rows, errors = parse_import(data, file.filename or "", project.mode, existing)
    if errors:
        raise HTTPException(
            422, {"message": "Import rejected; no rows were saved", "errors": errors}
        )
    db.add_all([Item(project_id=project_id, **row) for row in rows])
    return {"imported": len(rows)}


@router.get(
    "/projects/{project_id}/assignments/current",
    response_model=AssignmentOut | None,
    tags=["Assignments"],
)
async def current_assignment(
    project_id: str,
    user: User = Depends(annotator),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    project = await project_access(db, project_id, user)
    assignment = (
        await active_assignment(db, project_id, user.id) if project.state == "active" else None
    )
    return await assignment_out(db, assignment, project) if assignment else None


@router.post(
    "/projects/{project_id}/assignments/next",
    response_model=AssignmentOut | None,
    tags=["Assignments"],
)
async def next_assignment(
    project_id: str,
    user: User = Depends(annotator),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    await project_access(db, project_id, user)
    project = await lock_project(db, project_id)
    if not await db.get(Membership, (project_id, user.id), populate_existing=True):
        raise HTTPException(403, "You are not a member of this project")
    if project.state != "active":
        raise HTTPException(409, "This project is not active")
    current = await active_assignment(db, project_id, user.id)
    if current:
        return await assignment_out(db, current, project)
    items = (
        await db.scalars(
            select(Item).where(Item.project_id == project_id).order_by(Item.external_id)
        )
    ).all()
    assignments = (
        await db.scalars(select(Assignment).where(Assignment.project_id == project_id))
    ).all()
    submitted = (
        await db.scalars(
            select(Annotation).where(
                Annotation.project_id == project_id, Annotation.status == "submitted"
            )
        )
    ).all()
    completed_ids = {a.assignment_id for a in submitted}
    now = time.time()
    for item in items:
        prior = next(
            (a for a in assignments if a.item_id == item.id and a.user_id == user.id), None
        )
        if prior and (prior.id in completed_ids or prior.skipped):
            continue
        taken = sum(
            a.item_id == item.id
            and (a.id in completed_ids or (not a.skipped and a.expires_at > now))
            for a in assignments
        )
        if taken >= project.target_raters:
            continue
        if prior:
            prior.expires_at = now + LEASE_SECONDS
            prior.version += 1
            assignment = prior
        else:
            assignment = Assignment(
                project_id=project_id,
                item_id=item.id,
                user_id=user.id,
                expires_at=now + LEASE_SECONDS,
                swapped=bool(secrets.randbits(1)),
            )
            db.add(assignment)
        await db.flush()
        return await assignment_out(db, assignment, project)
    return None


async def writable_assignment(db, assignment_id, user):
    initial = await db.get(Assignment, assignment_id)
    if not initial or initial.user_id != user.id:
        raise HTTPException(404, "Assignment not found")
    project = await lock_project(db, initial.project_id)
    await project_access(db, project.id, user)
    assignment = await db.get(Assignment, assignment_id, populate_existing=True)
    annotation = await db.scalar(
        select(Annotation).where(Annotation.assignment_id == assignment_id)
    )
    if annotation and annotation.status == "submitted":
        raise HTTPException(409, "Submitted annotations are immutable")
    if project.state != "active" or assignment.skipped or assignment.expires_at <= time.time():
        raise HTTPException(409, "Claim expired or project closed; request the next assignment")
    return project, assignment, annotation


async def write_annotation(db, assignment_id, body, user, submit):
    project, assignment, annotation = await writable_assignment(db, assignment_id, user)
    if assignment.version != body.version:
        raise HTTPException(409, "Draft changed in another tab; reload this assignment")
    item = await db.get(Item, assignment.item_id)
    payload = canonical_payload(
        project, item, body.mode, body.payload.model_dump(), assignment.swapped
    )
    if not annotation:
        annotation = Annotation(
            assignment_id=assignment.id,
            project_id=project.id,
            item_id=item.id,
            user_id=user.id,
            payload=payload,
        )
        db.add(annotation)
    annotation.payload = payload
    annotation.status = "submitted" if submit else "draft"
    if submit:
        annotation.submitted_at = time.time()
        project.metric_revision += 1
    assignment.version += 1
    assignment.expires_at = time.time() + LEASE_SECONDS
    return {
        "version": assignment.version,
        "expires_at": assignment.expires_at,
        "status": annotation.status,
    }


@router.put("/assignments/{assignment_id}/draft", response_model=SaveOut, tags=["Assignments"])
async def save_draft(
    assignment_id: str,
    body: AnnotationWrite,
    user: User = Depends(annotator),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await write_annotation(db, assignment_id, body, user, False)


@router.post("/assignments/{assignment_id}/submit", response_model=SaveOut, tags=["Assignments"])
async def submit(
    assignment_id: str,
    body: AnnotationWrite,
    user: User = Depends(annotator),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await write_annotation(db, assignment_id, body, user, True)


@router.post("/assignments/{assignment_id}/skip", response_model=Message, tags=["Assignments"])
async def skip(
    assignment_id: str,
    user: User = Depends(annotator),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    _, assignment, _ = await writable_assignment(db, assignment_id, user)
    assignment.skipped = True
    assignment.expires_at = 0
    assignment.version += 1
    return {"message": "Assignment skipped"}


@router.post(
    "/projects/{project_id}/assignments/reset-skipped", response_model=Message, tags=["Assignments"]
)
async def reset_skipped(
    project_id: str,
    user: User = Depends(annotator),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    await project_access(db, project_id, user)
    await lock_project(db, project_id)
    for assignment in (
        await db.scalars(
            select(Assignment).where(
                Assignment.project_id == project_id,
                Assignment.user_id == user.id,
                Assignment.skipped.is_(True),
            )
        )
    ).all():
        assignment.skipped = False
    return {"message": "Skipped items are available again"}


@router.get("/projects/{project_id}/metrics", response_model=MetricsOut, tags=["Quality"])
async def get_metrics(
    project_id: str,
    user: User = Depends(reviewer),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await metrics(db, await project_access(db, project_id, user))


@router.get("/projects/{project_id}/review", response_model=list[ReviewItem], tags=["Quality"])
async def review_queue(
    project_id: str,
    all_items: bool = False,
    user: User = Depends(reviewer),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    project = await project_access(db, project_id, user)
    report = await metrics(db, project)
    items, annotations, decisions, users = await metric_data(db, project)
    names = {u.id: u.name for u in users}
    lookup = {i.id: i for i in items}
    decision_map = {d.item_id: d for d in decisions}
    out = []
    for metric in report["items"]:
        if not all_items and (metric["resolved"] or metric["submitted"] < project.target_raters):
            continue
        item = lookup[metric["item_id"]]
        decision = decision_map.get(item.id)
        out.append(
            {
                "item": {
                    "id": item.id,
                    "external_id": item.external_id,
                    "content": item.content,
                    "tokens": item.tokens,
                },
                "agreement": metric,
                "annotations": [
                    {"annotator": names[a.user_id], "payload": a.payload}
                    for a in annotations
                    if a.item_id == item.id
                ],
                "adjudication": {
                    "payload": decision.payload,
                    "rationale": decision.rationale,
                    "reviewer": names[decision.reviewer_id],
                }
                if decision
                else None,
            }
        )
    return out


@router.put(
    "/projects/{project_id}/items/{item_id}/adjudication", response_model=Message, tags=["Quality"]
)
async def adjudicate(
    project_id: str,
    item_id: str,
    body: DecisionWrite,
    user: User = Depends(reviewer),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    project = await lock_project(db, project_id)
    if project.state not in {"active", "completed"}:
        raise HTTPException(409, "Adjudication is available for active or completed projects")
    item = await db.get(Item, item_id)
    if not item or item.project_id != project_id:
        raise HTTPException(404, "Item not found")
    submitted = (
        await db.scalars(
            select(Annotation).where(
                Annotation.item_id == item_id, Annotation.status == "submitted"
            )
        )
    ).all()
    if len(submitted) < project.target_raters:
        raise HTTPException(409, "Wait for all raters before adjudicating")
    payload = canonical_payload(project, item, body.mode, body.payload.model_dump())
    decision = await db.get(Adjudication, item_id)
    if not decision:
        decision = Adjudication(
            item_id=item_id,
            project_id=project_id,
            reviewer_id=user.id,
            payload=payload,
            rationale=body.rationale,
        )
        db.add(decision)
    decision.payload, decision.rationale, decision.reviewer_id = payload, body.rationale, user.id
    decision.created_at = time.time()
    project.metric_revision += 1
    return {"message": "Adjudication saved"}


@router.get(
    "/projects/{project_id}/events",
    tags=["Quality"],
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def events(
    project_id: str,
    request: Request,
    user: User = Depends(reviewer),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    await project_access(db, project_id, user)
    token_hash = digest(request.cookies.get("concord_session", ""))
    await db.commit()  # Do not hold a database connection for the stream lifetime.

    async def stream():
        last = -1
        tick = 0
        while not await request.is_disconnected():
            async with SessionLocal() as poll:
                session = await poll.get(Session, token_hash)
                person = await poll.get(User, user.id)
                if (
                    not session
                    or session.expires_at <= time.time()
                    or not person
                    or person.role not in {"admin", "reviewer"}
                ):
                    yield "event: expired\ndata: {}\n\n"
                    return
                project = await poll.get(Project, project_id)
                if not project:
                    return
                revision = project.metric_revision
            if revision != last:
                yield f"id: {revision}\nevent: revision\ndata: {json.dumps({'revision': revision})}\n\n"
                last = revision
            elif tick % 10 == 0:
                yield ": keepalive\n\n"
            tick += 1
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/projects/{project_id}/exports",
    tags=["Exports"],
    responses={
        200: {
            "content": {
                "application/zip": {},
                "application/x-ndjson": {},
                "application/vnd.apache.parquet": {},
            }
        }
    },
)
async def export(
    project_id: str,
    format: Literal["jsonl", "parquet", "huggingface"] = "jsonl",
    selection: Literal["annotations", "consensus", "both"] = "both",
    include_unresolved: bool = False,
    user: User = Depends(reviewer),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    project = await lock_project(db, project_id)
    data = await metric_data(db, project)
    await db.commit()  # Snapshot is materialized; release the queue lock before encoding.
    content, media_type, filename = await run_in_threadpool(
        export_artifact, project, data, selection, format, include_unresolved
    )
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="concord-{filename}"',
            "Cache-Control": "no-store",
        },
    )
