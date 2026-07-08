"""
Target Pydantic schemas — request/response contracts for target endpoints.

Schemas:
    TargetCreate         → Create target (POST body)
    TargetUpdate         → Partial update (PATCH body)
    TargetResponse       → Full target API response
    TargetSummary        → Lightweight list-view representation
    TargetTagResponse    → Tag representation in API responses
    BulkTagUpdate        → Replace entire tag set
    TargetNoteUpdate     → Update scope_notes (dedicated endpoint)
    TargetDeactivate     → Deactivate with optional reason
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.target import TargetType
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel
from app.utils.target_validators import validate_tag, validate_target_value


# ── Tag Schema ────────────────────────────────────────────────────────────────

class TargetTagResponse(VulnForgeBaseModel):
    """Single tag as returned by the API."""

    id: UUID = Field(description="Tag record UUID.")
    target_id: UUID = Field(description="Parent target UUID.")
    tag: str = Field(description="Normalised tag label.")
    created_at: datetime = Field(description="UTC creation timestamp.")


# ── Request Schemas ────────────────────────────────────────────────────────────

class TargetCreate(VulnForgeBaseModel):
    """Payload for creating a new target.

    The ``value`` field is validated against ``target_type`` using the
    dedicated validator module.  Invalid values are rejected with a
    descriptive error before the record ever reaches the database.
    """

    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable label for this target.",
        examples=["Production Web Server", "Corporate VPN Gateway"],
    )
    target_type: TargetType = Field(
        description="Asset type classification.",
        examples=["host", "network", "url", "domain"],
    )
    value: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "The scannable value. Format depends on target_type:\n"
            "- **host**: IPv4 or IPv6 address (e.g., `192.168.1.1`)\n"
            "- **network**: CIDR notation (e.g., `10.0.0.0/24`)\n"
            "- **url**: HTTP/HTTPS URL (e.g., `https://app.example.com`)\n"
            "- **domain**: Domain name (e.g., `example.com`, `*.example.com`)"
        ),
        examples=["192.168.1.100", "10.0.0.0/24", "https://app.example.com", "example.com"],
    )
    description: str | None = Field(
        default=None,
        description="Optional description of this target asset.",
    )
    scope_notes: str | None = Field(
        default=None,
        description="Authorization notes and explicit out-of-scope exclusions.",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional list of labels (max 20). Auto-normalised to lowercase.",
        examples=[["production", "web-app", "external"]],
    )
    workspace_id: UUID | None = Field(
        default=None,
        description="Optional workspace to associate this target with.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("tags", mode="before")
    @classmethod
    def validate_and_normalise_tags(cls, v: list) -> list[str]:
        """Validate and normalise each tag in the list.

        Args:
            v: Raw list of tag strings.

        Returns:
            list[str]: Deduplicated, normalised tags.

        Raises:
            ValueError: If any tag is invalid.
        """
        if not v:
            return []
        validated = []
        seen: set[str] = set()
        for raw_tag in v:
            if not isinstance(raw_tag, str):
                raise ValueError(f"Tags must be strings, got {type(raw_tag).__name__}.")
            normalised = validate_tag(raw_tag)
            if normalised not in seen:
                seen.add(normalised)
                validated.append(normalised)
        return validated

    @model_validator(mode="after")
    def validate_value_for_type(self) -> "TargetCreate":
        """Cross-field validation: validate value against target_type.

        Returns:
            TargetCreate: Self with normalised value.

        Raises:
            ValueError: If value is invalid for the declared target_type.
        """
        self.value = validate_target_value(self.target_type.value, self.value)
        return self


class TargetUpdate(VulnForgeBaseModel):
    """Partial update payload for an existing target.

    Only provided fields are updated.
    Note: ``target_type`` and ``value`` cannot be changed independently —
    both must be provided together to trigger re-validation.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Updated human-readable label.",
    )
    description: str | None = Field(
        default=None,
        description="Updated description.",
    )
    scope_notes: str | None = Field(
        default=None,
        description="Updated authorization/scope notes.",
    )
    target_type: TargetType | None = Field(
        default=None,
        description="Updated target type (must be provided together with value).",
    )
    value: str | None = Field(
        default=None,
        max_length=500,
        description="Updated target value (must be provided together with target_type).",
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        return v.strip() if v else v

    @model_validator(mode="after")
    def validate_type_value_pair(self) -> "TargetUpdate":
        """Ensure target_type and value are always changed together.

        Returns:
            TargetUpdate: Self with re-validated value if both fields present.

        Raises:
            ValueError: If only one of target_type/value is provided,
                        or if the value is invalid for the type.
        """
        has_type = self.target_type is not None
        has_value = self.value is not None

        if has_type and not has_value:
            raise ValueError(
                "When updating 'target_type', 'value' must also be provided."
            )
        if has_value and not has_type:
            raise ValueError(
                "When updating 'value', 'target_type' must also be provided."
            )
        if has_type and has_value:
            self.value = validate_target_value(self.target_type.value, self.value)  # type: ignore[arg-type]
        return self


class BulkTagUpdate(VulnForgeBaseModel):
    """Replace the entire tag set for a target.

    PUT semantics — all existing tags are removed and replaced with this list.
    Use the individual tag add/remove endpoints for surgical updates.
    """

    tags: list[str] = Field(
        max_length=20,
        description="Complete replacement tag set (max 20). Empties all tags if [].",
        examples=[["production", "web-app", "external"]],
    )

    @field_validator("tags", mode="before")
    @classmethod
    def validate_and_normalise_tags(cls, v: list) -> list[str]:
        """Validate and deduplicate tags."""
        if not v:
            return []
        validated = []
        seen: set[str] = set()
        for raw_tag in v:
            normalised = validate_tag(str(raw_tag))
            if normalised not in seen:
                seen.add(normalised)
                validated.append(normalised)
        return validated


class TargetDeactivate(VulnForgeBaseModel):
    """Deactivate a target with an optional reason."""

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional reason for deactivation (stored in scope_notes).",
    )


# ── Response Schemas ───────────────────────────────────────────────────────────

class TargetResponse(TimestampedResponse):
    """Full target representation returned by the API."""

    name: str = Field(description="Human-readable target label.")
    target_type: TargetType = Field(description="Asset type classification.")
    value: str = Field(description="The validated, normalised scannable value.")
    description: str | None = Field(description="Asset description.")
    scope_notes: str | None = Field(description="Authorization notes.")
    is_active: bool = Field(description="Whether this target is available for scanning.")
    created_by_id: UUID = Field(description="UUID of the user who registered this target.")
    tags: list[TargetTagResponse] = Field(
        default_factory=list,
        description="Associated tag labels.",
    )
    scan_count: int = Field(
        default=0,
        description="Total number of scans run against this target.",
    )
    open_vulnerability_count: int = Field(
        default=0,
        description="Number of open/confirmed vulnerabilities on this target.",
    )


class TargetSummary(VulnForgeBaseModel):
    """Lightweight target representation for list views."""

    id: UUID
    name: str
    target_type: TargetType
    value: str
    is_active: bool
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(
        default_factory=list,
        description="Tag label strings (not full TargetTag objects).",
    )
    scan_count: int = Field(default=0)
    open_vulnerability_count: int = Field(default=0)
