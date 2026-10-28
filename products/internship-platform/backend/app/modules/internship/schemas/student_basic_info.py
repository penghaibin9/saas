"""Independent basic information commands: explicit version, no client-chosen identity."""
from pydantic import BaseModel, ConfigDict, Field, StrictInt


class StudentBasicInfoUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expectedVersion: StrictInt = Field(..., ge=0)
    sourceRegion: str = Field(..., max_length=100)
    nation: str = Field(..., max_length=50)
    gender: str = Field(..., max_length=10)


class StudentBasicInfoImport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    batchId: str = Field(..., min_length=1)
    rows: list[dict] = Field(..., min_length=1, max_length=1000)
