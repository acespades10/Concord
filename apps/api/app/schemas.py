from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: Literal["admin", "reviewer", "annotator"]
    model_config = ConfigDict(from_attributes=True)


class SessionOut(BaseModel):
    user: UserOut
    csrf: str


class ProjectConfig(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    mode: Literal["rating", "ner", "ab"]
    labels: list[str] = Field(default_factory=list, max_length=30)
    ordered: bool = False
    target_raters: int = Field(default=3, ge=2, le=20)
    review_threshold: float = Field(default=0.8, ge=0.5, le=1)

    @field_validator("labels")
    @classmethod
    def valid_labels(cls, value):
        if any(not x.strip() or len(x) > 60 or x != x.strip() for x in value):
            raise ValueError("Labels must contain 1–60 characters without surrounding spaces")
        if len(set(value)) != len(value):
            raise ValueError("Labels must be unique")
        return value


class ProjectOut(ProjectConfig):
    description: str
    labels: list[str]
    ordered: bool
    target_raters: int
    review_threshold: float
    id: str
    state: Literal["draft", "active", "completed", "archived"]
    metric_revision: int
    item_count: int
    submission_count: int
    my_submission_count: int
    member_count: int
    model_config = ConfigDict(from_attributes=True)


class StateChange(StrictModel):
    state: Literal["active", "completed", "archived"]


class Members(StrictModel):
    user_ids: list[str]


class RatingPayload(StrictModel):
    label: str
    note: str = Field(default="", max_length=2000)


class ABPayload(StrictModel):
    choice: Literal["A", "B", "TIE"]
    note: str = Field(default="", max_length=2000)


class Span(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    label: str
    text: str


class NERPayload(StrictModel):
    spans: list[Span] = Field(max_length=500)


class RatingWrite(StrictModel):
    mode: Literal["rating"]
    payload: RatingPayload
    version: int = Field(ge=0)


class ABWrite(StrictModel):
    mode: Literal["ab"]
    payload: ABPayload
    version: int = Field(ge=0)


class NERWrite(StrictModel):
    mode: Literal["ner"]
    payload: NERPayload
    version: int = Field(ge=0)


AnnotationWrite = Annotated[RatingWrite | ABWrite | NERWrite, Field(discriminator="mode")]


class RatingDecision(StrictModel):
    mode: Literal["rating"]
    payload: RatingPayload
    rationale: str = Field(min_length=3, max_length=4000)


class ABDecision(StrictModel):
    mode: Literal["ab"]
    payload: ABPayload
    rationale: str = Field(min_length=3, max_length=4000)


class NERDecision(StrictModel):
    mode: Literal["ner"]
    payload: NERPayload
    rationale: str = Field(min_length=3, max_length=4000)


DecisionWrite = Annotated[RatingDecision | ABDecision | NERDecision, Field(discriminator="mode")]


class Token(BaseModel):
    start: int
    end: int
    text: str


class ItemOut(BaseModel):
    id: str
    external_id: str
    content: dict[str, str]
    tokens: list[Token]


class AssignmentOut(BaseModel):
    id: str
    project_id: str
    version: int
    expires_at: float
    item: ItemOut
    draft: RatingPayload | ABPayload | NERPayload | None


class SaveOut(BaseModel):
    version: int
    expires_at: float
    status: Literal["draft", "submitted"]


class Kappa(BaseModel):
    value: float | None
    reason: str | None = None
    n: int


class PairMetric(BaseModel):
    left: str
    right: str
    shared_items: int
    kappa: Kappa
    span_f1: float | None = None


class ItemMetric(BaseModel):
    item_id: str
    external_id: str
    submitted: int
    vote_share: float
    resolved: bool
    reason: str | None
    payload: dict | None
    adjudicated: bool


class MetricsOut(BaseModel):
    revision: int
    total_items: int
    submissions: int
    expected_submissions: int
    fully_rated: int
    resolved: int
    unresolved: int
    coverage: float
    fleiss: Kappa
    distribution: dict[str, int]
    annotators: dict[str, str]
    pairs: list[PairMetric]
    items: list[ItemMetric]


class ReviewAnnotation(BaseModel):
    annotator: str
    payload: dict


class ReviewItem(BaseModel):
    item: ItemOut
    agreement: ItemMetric
    annotations: list[ReviewAnnotation]
    adjudication: dict | None


class ImportResult(BaseModel):
    imported: int


class Message(BaseModel):
    message: str
