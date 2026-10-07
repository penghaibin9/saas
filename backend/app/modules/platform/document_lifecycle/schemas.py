from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    fileVersionId: int = Field(gt=0)
    expectedSha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class ComparisonRequest(BaseModel):
    leftFileVersionId: int = Field(gt=0)
    leftExpectedSha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    rightFileVersionId: int = Field(gt=0)
    rightExpectedSha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
