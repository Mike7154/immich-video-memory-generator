"""Cross-account identities used to treat separate face clusters as one person."""

from __future__ import annotations

import calendar
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


class FloatingAnnualEventConfig(BaseModel):
    """A yearly event described by its weekday occurrence within a month."""

    month: int = Field(ge=1, le=12)
    weekday: Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    occurrence: int = Field(ge=1, le=5)

    def date_for_year(self, year: int) -> date:
        """Resolve this rule in one year, rejecting an absent fifth occurrence."""
        weekday_index = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }[self.weekday]
        first = date(year, self.month, 1)
        day = 1 + (weekday_index - first.weekday()) % 7 + 7 * (self.occurrence - 1)
        if day > calendar.monthrange(year, self.month)[1]:
            raise ValueError(
                f"{self.occurrence} occurrence of {self.weekday} does not exist "
                f"in {year}-{self.month:02d}"
            )
        return date(year, self.month, day)


class IdentityGroupConfig(BaseModel):
    """Saved Boolean selection over logical subjects."""

    display_name: str
    subjects: list[str] = Field(default_factory=list)
    match: Literal["any", "all"] = "any"
    required: list[str] = Field(default_factory=list)
    any_of: list[str] = Field(default_factory=list)
    event_date: date | None = None
    event_rule: FloatingAnnualEventConfig | None = None

    @model_validator(mode="after")
    def validate_boolean_expression(self) -> IdentityGroupConfig:
        composite = bool(self.required or self.any_of)
        if self.subjects and composite:
            raise ValueError("Use either subjects+match or required+any_of, not both")
        if not self.subjects and not composite:
            raise ValueError("An identity group needs subjects or required/any_of")
        if overlap := set(self.required) & set(self.any_of):
            raise ValueError(
                "Subjects cannot be both required and any_of: " + ", ".join(sorted(overlap))
            )
        if self.event_date is not None and self.event_rule is not None:
            raise ValueError("Use either event_date or event_rule, not both")
        return self

    @property
    def referenced_subjects(self) -> list[str]:
        """Return every logical subject named by either Boolean syntax."""
        return [*self.subjects, *self.required, *self.any_of]

    @property
    def boolean_label(self) -> str:
        """Human-readable label for selectors without exposing query internals."""
        return "REQUIRED + ANY" if self.required or self.any_of else self.match.upper()


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
            for subject in group.referenced_subjects
            if subject not in self.subjects
        }
        if unknown_subjects:
            names = ", ".join(sorted(unknown_subjects))
            raise ValueError(f"Unknown logical subjects: {names}")
        return self
