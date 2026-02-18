"""Label-related schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LabelResponse(BaseModel):
    """Label detail response."""

    id: str
    names: list[str] = Field(default_factory=list)
    is_implicit: bool = False
    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    post_count: int = Field(default=0, ge=0)


class LabelGraphNode(BaseModel):
    """Node in the label DAG for visualization."""

    id: str
    names: list[str] = Field(default_factory=list)
    post_count: int = Field(default=0, ge=0)


class LabelGraphEdge(BaseModel):
    """Edge in the label DAG."""

    source: str  # child label_id
    target: str  # parent label_id


class LabelGraphResponse(BaseModel):
    """Full label DAG for graph visualization."""

    nodes: list[LabelGraphNode]
    edges: list[LabelGraphEdge]


class LabelCreate(BaseModel):
    """Request to create a new label."""

    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
