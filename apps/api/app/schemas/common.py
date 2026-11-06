"""Shared API contracts (API-05)."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict


class Page[T](BaseModel):
    """Offset pagination. `total` is the full count of matching rows."""

    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int
    offset: int


def page_params(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)
