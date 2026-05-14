"""Typed Pydantic models for monday.com API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Column(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    title: str
    type: str
    settings_str: str = ""


class ColumnValue(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    column_id: str = Field(alias="id")
    type: str
    value: str | None = None
    text: str | None = None


class Item(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    name: str
    state: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    column_values: list[ColumnValue] = Field(default_factory=list)


class Board(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    name: str
    workspace_id: str = ""
    columns: list[Column] = Field(default_factory=list)
