from __future__ import annotations

from datetime import datetime
from typing import Annotated, ClassVar

from pydantic import Field

from ..models.enums import DifficultyLevel, KnowledgeLifecycleStatus
from .common import (
    NameString,
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    RequiredText,
    SlugString,
    TitleString,
    TypeString,
)


NonNegativeFloat = Annotated[float, Field(ge=0.0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class LearningObjectiveBase(ORMResponse):
    lesson_id: PositiveId
    objective: RequiredText
    display_order: NonNegativeInt = 0


class LearningObjectiveCreate(LearningObjectiveBase):
    pass


class LearningObjectiveUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        LearningObjectiveBase.model_fields
    )

    lesson_id: PositiveId | None = None
    objective: RequiredText | None = None
    display_order: NonNegativeInt | None = None


class LearningObjectiveRead(LearningObjectiveBase):
    id: int


class LessonPrerequisiteBase(ORMResponse):
    lesson_id: PositiveId
    prerequisite_lesson_id: PositiveId


class LessonPrerequisiteCreate(LessonPrerequisiteBase):
    pass


class LessonPrerequisiteUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        LessonPrerequisiteBase.model_fields
    )

    lesson_id: PositiveId | None = None
    prerequisite_lesson_id: PositiveId | None = None


class LessonPrerequisiteRead(LessonPrerequisiteBase):
    id: int


class CurriculumPathLessonBase(ORMResponse):
    curriculum_path_id: PositiveId
    lesson_id: PositiveId
    display_order: NonNegativeInt


class CurriculumPathLessonCreate(CurriculumPathLessonBase):
    pass


class CurriculumPathLessonUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        CurriculumPathLessonBase.model_fields
    )

    curriculum_path_id: PositiveId | None = None
    lesson_id: PositiveId | None = None
    display_order: NonNegativeInt | None = None


class CurriculumPathLessonRead(CurriculumPathLessonBase):
    pass


class LessonBase(ORMResponse):
    module_id: PositiveId
    knowledge_article_id: PositiveId | None = None
    concept_id: PositiveId | None = None
    title: TitleString
    slug: SlugString
    summary: str | None = None
    estimated_minutes: NonNegativeInt = 0
    difficulty_level: DifficultyLevel = DifficultyLevel.BEGINNER
    status: KnowledgeLifecycleStatus = KnowledgeLifecycleStatus.DRAFT
    display_order: NonNegativeInt = 0


class LessonCreate(LessonBase):
    pass


class LessonUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "module_id",
            "title",
            "slug",
            "estimated_minutes",
            "difficulty_level",
            "status",
            "display_order",
        }
    )

    module_id: PositiveId | None = None
    knowledge_article_id: PositiveId | None = None
    concept_id: PositiveId | None = None
    title: TitleString | None = None
    slug: SlugString | None = None
    summary: str | None = None
    estimated_minutes: NonNegativeInt | None = None
    difficulty_level: DifficultyLevel | None = None
    status: KnowledgeLifecycleStatus | None = None
    display_order: NonNegativeInt | None = None


class LessonRead(LessonBase):
    id: int
    created_at: datetime
    updated_at: datetime
    objectives: list[LearningObjectiveRead] = Field(default_factory=list)
    prerequisite_links: list[LessonPrerequisiteRead] = Field(
        default_factory=list
    )


class ModuleBase(ORMResponse):
    course_id: PositiveId
    name: NameString
    slug: SlugString
    description: str | None = None
    estimated_minutes: NonNegativeInt = 0
    display_order: NonNegativeInt = 0


class ModuleCreate(ModuleBase):
    pass


class ModuleUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "course_id",
            "name",
            "slug",
            "estimated_minutes",
            "display_order",
        }
    )

    course_id: PositiveId | None = None
    name: NameString | None = None
    slug: SlugString | None = None
    description: str | None = None
    estimated_minutes: NonNegativeInt | None = None
    display_order: NonNegativeInt | None = None


class ModuleRead(ModuleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    lessons: list[LessonRead] = Field(default_factory=list)


class CourseBase(ORMResponse):
    degree_id: PositiveId
    name: NameString
    slug: SlugString
    description: str | None = None
    estimated_hours: NonNegativeFloat = 0.0
    display_order: NonNegativeInt = 0


class CourseCreate(CourseBase):
    pass


class CourseUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "degree_id",
            "name",
            "slug",
            "estimated_hours",
            "display_order",
        }
    )

    degree_id: PositiveId | None = None
    name: NameString | None = None
    slug: SlugString | None = None
    description: str | None = None
    estimated_hours: NonNegativeFloat | None = None
    display_order: NonNegativeInt | None = None


class CourseRead(CourseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    modules: list[ModuleRead] = Field(default_factory=list)


class DegreeBase(ORMResponse):
    school_id: PositiveId
    name: NameString
    slug: SlugString
    description: str | None = None
    level: TypeString
    estimated_hours: NonNegativeFloat = 0.0
    display_order: NonNegativeInt = 0


class DegreeCreate(DegreeBase):
    pass


class DegreeUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "school_id",
            "name",
            "slug",
            "level",
            "estimated_hours",
            "display_order",
        }
    )

    school_id: PositiveId | None = None
    name: NameString | None = None
    slug: SlugString | None = None
    description: str | None = None
    level: TypeString | None = None
    estimated_hours: NonNegativeFloat | None = None
    display_order: NonNegativeInt | None = None


class DegreeRead(DegreeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    courses: list[CourseRead] = Field(default_factory=list)


class SchoolBase(ORMResponse):
    name: NameString
    slug: SlugString
    description: str | None = None
    icon: NameString | None = None
    display_order: NonNegativeInt = 0
    is_active: bool = True


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "slug", "display_order", "is_active"}
    )

    name: NameString | None = None
    slug: SlugString | None = None
    description: str | None = None
    icon: NameString | None = None
    display_order: NonNegativeInt | None = None
    is_active: bool | None = None


class SchoolRead(SchoolBase):
    id: int
    created_at: datetime
    updated_at: datetime
    degrees: list[DegreeRead] = Field(default_factory=list)


class CurriculumPathBase(ORMResponse):
    name: NameString
    slug: SlugString
    description: str | None = None


class CurriculumPathCreate(CurriculumPathBase):
    pass


class CurriculumPathUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "slug"}
    )

    name: NameString | None = None
    slug: SlugString | None = None
    description: str | None = None


class CurriculumPathRead(CurriculumPathBase):
    id: int
    created_at: datetime
    lesson_links: list[CurriculumPathLessonRead] = Field(default_factory=list)


LearningObjectiveResponse = LearningObjectiveRead
LessonPrerequisiteResponse = LessonPrerequisiteRead
CurriculumPathLessonResponse = CurriculumPathLessonRead
LessonResponse = LessonRead
ModuleResponse = ModuleRead
CourseResponse = CourseRead
DegreeResponse = DegreeRead
SchoolResponse = SchoolRead
CurriculumPathResponse = CurriculumPathRead


__all__ = [
    "CourseBase",
    "CourseCreate",
    "CourseRead",
    "CourseResponse",
    "CourseUpdate",
    "CurriculumPathBase",
    "CurriculumPathCreate",
    "CurriculumPathLessonBase",
    "CurriculumPathLessonCreate",
    "CurriculumPathLessonRead",
    "CurriculumPathLessonResponse",
    "CurriculumPathLessonUpdate",
    "CurriculumPathRead",
    "CurriculumPathResponse",
    "CurriculumPathUpdate",
    "DegreeBase",
    "DegreeCreate",
    "DegreeRead",
    "DegreeResponse",
    "DegreeUpdate",
    "LearningObjectiveBase",
    "LearningObjectiveCreate",
    "LearningObjectiveRead",
    "LearningObjectiveResponse",
    "LearningObjectiveUpdate",
    "LessonBase",
    "LessonCreate",
    "LessonPrerequisiteBase",
    "LessonPrerequisiteCreate",
    "LessonPrerequisiteRead",
    "LessonPrerequisiteResponse",
    "LessonPrerequisiteUpdate",
    "LessonRead",
    "LessonResponse",
    "LessonUpdate",
    "ModuleBase",
    "ModuleCreate",
    "ModuleRead",
    "ModuleResponse",
    "ModuleUpdate",
    "SchoolBase",
    "SchoolCreate",
    "SchoolRead",
    "SchoolResponse",
    "SchoolUpdate",
]
