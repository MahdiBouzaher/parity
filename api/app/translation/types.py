from dataclasses import dataclass, field
from typing import Literal

Lang = Literal["sas", "vba"]
RiskTag = Literal["rounding", "missing values", "sort order", "integer division", "dates"]


class TranslateError(Exception):
    pass


@dataclass
class RiskyLine:
    line: int
    tag: str
    reason: str


@dataclass
class Hint:
    line: int
    kind: str
    text: str
    python: str | None


@dataclass
class Analysis:
    lang: str
    statements: int
    hints: list[Hint]
    risky_lines: list[RiskyLine]
    input_name: str | None
    output_tables: list[str]
    draft_python: str


@dataclass
class TranslateContext:
    filename: str
    input_columns: list[str]
    input_dtypes: dict[str, str]
    expected_tables: dict[str, list[str]]


@dataclass
class Hunk:
    start: int
    remove: list[str]
    add: list[str]


@dataclass
class Patch:
    summary: str
    hunks: list[Hunk]


@dataclass
class Explanation:
    source: Literal["model", "rules", "none"]
    tag: str | None
    title: str
    paragraphs: list[str] = field(default_factory=list)
    note: str = ""
    fixed_body: str = ""
