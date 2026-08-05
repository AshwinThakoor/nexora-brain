from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class AcademyORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


ItemT = TypeVar("ItemT")


class AcademyPage(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    skip: int = Field(ge=0)


class LessonSummary(AcademyORMResponse):
    id: int
    module_id: int
    title: str
    slug: str
    summary: str | None
    estimated_minutes: int
    difficulty_level: str
    status: str
    display_order: int


class LessonDetail(LessonSummary):
    knowledge_article_id: int | None
    concept_id: int | None
    objectives: list["LearningObjectiveItem"] = Field(default_factory=list)
    prerequisites: list[LessonSummary] = Field(default_factory=list)


class LearningObjectiveItem(AcademyORMResponse):
    id: int
    objective: str
    display_order: int


class ModuleSummary(AcademyORMResponse):
    id: int
    course_id: int
    name: str
    slug: str
    description: str | None
    estimated_minutes: int
    display_order: int


class ModuleDetail(ModuleSummary):
    lessons: list[LessonSummary] = Field(default_factory=list)


class CourseSummary(AcademyORMResponse):
    id: int
    degree_id: int
    name: str
    slug: str
    description: str | None
    estimated_hours: float
    display_order: int


class CourseDetail(CourseSummary):
    modules: list[ModuleSummary] = Field(default_factory=list)


class DegreeSummary(AcademyORMResponse):
    id: int
    school_id: int
    name: str
    slug: str
    description: str | None
    level: str
    estimated_hours: float
    display_order: int


class DegreeDetail(DegreeSummary):
    courses: list[CourseSummary] = Field(default_factory=list)


class SchoolSummary(AcademyORMResponse):
    id: int
    name: str
    slug: str
    description: str | None
    icon: str | None
    display_order: int
    is_active: bool


class SchoolDetail(SchoolSummary):
    degrees: list[DegreeSummary] = Field(default_factory=list)


class CurriculumPathSummary(AcademyORMResponse):
    id: int
    name: str
    slug: str
    description: str | None
    created_at: datetime


class CurriculumPathDetail(CurriculumPathSummary):
    lessons: list[LessonSummary] = Field(default_factory=list)


__all__ = [
    "AcademyPage",
    "CourseDetail",
    "CourseSummary",
    "CurriculumPathDetail",
    "CurriculumPathSummary",
    "DegreeDetail",
    "DegreeSummary",
    "LearningObjectiveItem",
    "LessonDetail",
    "LessonSummary",
    "ModuleDetail",
    "ModuleSummary",
    "SchoolDetail",
    "SchoolSummary",
]
