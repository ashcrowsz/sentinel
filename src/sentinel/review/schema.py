from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Category(StrEnum):
    bug = "bug"
    security = "security"
    missing_test = "missing_test"
    performance = "performance"


SEVERITY_ICON = {"critical": "🛑", "high": "⚠️", "medium": "🔎", "low": "💡"}


class Finding(BaseModel):
    file: str
    line: int = Field(ge=1)
    # last line the suggestion replaces (inclusive); None = just `line`
    end_line: int | None = Field(default=None, ge=1)
    severity: Severity
    category: Category
    comment: str = Field(min_length=10, max_length=1200)
    suggestion: str | None = None
    confidence: float = Field(ge=0, le=1)

    def to_github_comment(self) -> dict[str, Any]:
        icon = SEVERITY_ICON[self.severity.value]
        label = self.category.value.replace("_", " ")
        body = f"{icon} **{label}** ({self.severity.value})\n\n{self.comment}"
        if self.suggestion:
            body += "\n\n```suggestion\n" + self.suggestion + "\n```"
        comment: dict[str, Any] = {"path": self.file, "side": "RIGHT", "body": body}
        if self.end_line and self.end_line > self.line:
            # multi-line comment: GitHub's suggestion then replaces the whole range
            comment.update(start_line=self.line, start_side="RIGHT", line=self.end_line)
        else:
            comment["line"] = self.line
        return comment


class ReviewOutput(BaseModel):
    summary: str
    findings: list[Finding]


REVIEW_JSON_SCHEMA: dict[str, Any] = ReviewOutput.model_json_schema()
