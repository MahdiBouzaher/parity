from pydantic import BaseModel


class RunCreate(BaseModel):
    lang: str
    filename: str
    source: str
    dataset_id: str


class SampleCreate(BaseModel):
    lang: str


class TolerancesUpdate(BaseModel):
    tolerances: dict[str, float]


class KeepBody(BaseModel):
    reason: str = ""
