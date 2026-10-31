"""The optional location is a single explicit capture, never a background tracker."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class VisitLocation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consent: StrictBool
    latitude: float = Field(strict=True, ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(strict=True, ge=-180, le=180, allow_inf_nan=False)
    accuracyM: float = Field(strict=True, ge=0, allow_inf_nan=False)
    coordinateSystem: Literal['WGS84', 'GCJ02']
    capturedAt: datetime

    @model_validator(mode='after')
    def explicit_capture(self):
        if self.consent is not True or self.capturedAt.utcoffset() is None:
            raise ValueError('须主动同意登记位置，采集时间须包含时区')
        return self


class VisitLocationDisclosure(BaseModel):
    model_config = ConfigDict(extra='forbid')
    batchId: int = Field(gt=0)
    expectedVersion: int = Field(strict=True, ge=0)
    reason: str = Field(min_length=5, max_length=200)
