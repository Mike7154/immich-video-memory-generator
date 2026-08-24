"""Cross-account identities used to treat separate face clusters as one person."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from immich_memories.api.compatibility import ApiVersionPolicy
from immich_memories.config_models import expand_env_vars


class IdentityAccountConfig(BaseModel):
    """Credentials used only to discover an account's private person clusters."""

    api_key: str
    url: str | None = None
    api_version: ApiVersionPolicy | None = None

    @field_validator("api_key", "url", mode="before")
    @classmethod
    def expand_env(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return expand_env_vars(value)
        return value


class LogicalSubjectConfig(BaseModel):
    """One real person mapped to that person's Immich ID in each account."""

    display_name: str
    people: dict[str, str] = Field(min_length=1)
    birth_date: date | None = None


class IdentityGroupConfig(BaseModel):
    """Saved Boolean selection over logical subjects."""

    display_name: str
    subjects: list[str] = Field(min_length=1)
    match: Literal["any", "all"] = "any"
    event_date: date | None = None


class IdentityConfig(BaseModel):
    """Named accounts, logical people, and reusable Boolean groups."""

    accounts: dict[str, IdentityAccountConfig] = Field(default_factory=dict)
    subjects: dict[str, LogicalSubjectConfig] = Field(default_factory=dict)
    groups: dict[str, IdentityGroupConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> IdentityConfig:
        unknown_accounts = {
            account
            for subject in self.subjects.values()
            for account in subject.people
            if account not in self.accounts
        }
        if unknown_accounts:
            names = ", ".join(sorted(unknown_accounts))
            raise ValueError(f"Unknown identity accounts: {names}")

        unknown_subjects = {
            subject
            for group in self.groups.values()
            for subject in group.subjects
            if subject not in self.subjects
        }
        if unknown_subjects:
            names = ", ".join(sorted(unknown_subjects))
            raise ValueError(f"Unknown logical subjects: {names}")
        return self
