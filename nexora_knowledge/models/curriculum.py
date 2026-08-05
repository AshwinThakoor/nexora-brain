from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import CreatedAtMixin, TimestampMixin
from .enums import DifficultyLevel, KnowledgeLifecycleStatus


class School(TimestampMixin, Base):
    __tablename__ = "schools"
    __table_args__ = (
        CheckConstraint(
            "display_order >= 0",
            name="ck_schools_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(255))
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    degrees: Mapped[list["Degree"]] = relationship(
        "Degree",
        back_populates="school",
        cascade="all, delete-orphan",
        order_by="(Degree.display_order, Degree.id)",
    )


class Degree(TimestampMixin, Base):
    __tablename__ = "degrees"
    __table_args__ = (
        CheckConstraint(
            "estimated_hours >= 0",
            name="ck_degrees_estimated_hours_nonnegative",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="ck_degrees_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(100), nullable=False)
    estimated_hours: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    school: Mapped[School] = relationship(
        "School",
        back_populates="degrees",
    )
    courses: Mapped[list["Course"]] = relationship(
        "Course",
        back_populates="degree",
        cascade="all, delete-orphan",
        order_by="(Course.display_order, Course.id)",
    )


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "estimated_hours >= 0",
            name="ck_courses_estimated_hours_nonnegative",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="ck_courses_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    degree_id: Mapped[int] = mapped_column(
        ForeignKey("degrees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    estimated_hours: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    degree: Mapped[Degree] = relationship(
        "Degree",
        back_populates="courses",
    )
    modules: Mapped[list["Module"]] = relationship(
        "Module",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="(Module.display_order, Module.id)",
    )


class Module(TimestampMixin, Base):
    __tablename__ = "modules"
    __table_args__ = (
        CheckConstraint(
            "estimated_minutes >= 0",
            name="ck_modules_estimated_minutes_nonnegative",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="ck_modules_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    estimated_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    course: Mapped[Course] = relationship(
        "Course",
        back_populates="modules",
    )
    lessons: Mapped[list["Lesson"]] = relationship(
        "Lesson",
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="(Lesson.display_order, Lesson.id)",
    )


class Lesson(TimestampMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (
        CheckConstraint(
            "estimated_minutes >= 0",
            name="ck_lessons_estimated_minutes_nonnegative",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="ck_lessons_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_article_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    estimated_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    difficulty_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=DifficultyLevel.BEGINNER.value,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=KnowledgeLifecycleStatus.DRAFT.value,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    module: Mapped[Module] = relationship(
        "Module",
        back_populates="lessons",
    )
    knowledge_article: Mapped["KnowledgeArticle | None"] = relationship(
        "KnowledgeArticle",
        back_populates="lessons",
    )
    concept: Mapped["Concept | None"] = relationship(
        "Concept",
        back_populates="lessons",
    )
    objectives: Mapped[list["LearningObjective"]] = relationship(
        "LearningObjective",
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="(LearningObjective.display_order, LearningObjective.id)",
    )
    prerequisite_links: Mapped[list["LessonPrerequisite"]] = relationship(
        "LessonPrerequisite",
        foreign_keys="LessonPrerequisite.lesson_id",
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="LessonPrerequisite.id",
    )
    dependent_links: Mapped[list["LessonPrerequisite"]] = relationship(
        "LessonPrerequisite",
        foreign_keys="LessonPrerequisite.prerequisite_lesson_id",
        back_populates="prerequisite_lesson",
        cascade="all, delete-orphan",
        order_by="LessonPrerequisite.id",
    )
    prerequisites: Mapped[list["Lesson"]] = relationship(
        "Lesson",
        secondary="lesson_prerequisites",
        primaryjoin="Lesson.id == LessonPrerequisite.lesson_id",
        secondaryjoin=(
            "Lesson.id == LessonPrerequisite.prerequisite_lesson_id"
        ),
        order_by="LessonPrerequisite.id",
        viewonly=True,
    )
    dependents: Mapped[list["Lesson"]] = relationship(
        "Lesson",
        secondary="lesson_prerequisites",
        primaryjoin=(
            "Lesson.id == LessonPrerequisite.prerequisite_lesson_id"
        ),
        secondaryjoin="Lesson.id == LessonPrerequisite.lesson_id",
        order_by="LessonPrerequisite.id",
        viewonly=True,
    )
    curriculum_path_links: Mapped[list["CurriculumPathLesson"]] = relationship(
        "CurriculumPathLesson",
        back_populates="lesson",
        cascade="all, delete-orphan",
    )
    curriculum_paths: Mapped[list["CurriculumPath"]] = relationship(
        "CurriculumPath",
        secondary="curriculum_path_lessons",
        back_populates="lessons",
        viewonly=True,
    )


class LearningObjective(Base):
    __tablename__ = "learning_objectives"
    __table_args__ = (
        CheckConstraint(
            "display_order >= 0",
            name="ck_learning_objectives_display_order_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    lesson: Mapped[Lesson] = relationship(
        "Lesson",
        back_populates="objectives",
    )


class LessonPrerequisite(Base):
    __tablename__ = "lesson_prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "lesson_id",
            "prerequisite_lesson_id",
            name="uq_lesson_prerequisite_pair",
        ),
        CheckConstraint(
            "lesson_id != prerequisite_lesson_id",
            name="ck_lesson_prerequisite_not_self",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prerequisite_lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lesson: Mapped[Lesson] = relationship(
        "Lesson",
        foreign_keys=[lesson_id],
        back_populates="prerequisite_links",
    )
    prerequisite_lesson: Mapped[Lesson] = relationship(
        "Lesson",
        foreign_keys=[prerequisite_lesson_id],
        back_populates="dependent_links",
    )


class CurriculumPath(CreatedAtMixin, Base):
    __tablename__ = "curriculum_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)

    lesson_links: Mapped[list["CurriculumPathLesson"]] = relationship(
        "CurriculumPathLesson",
        back_populates="curriculum_path",
        cascade="all, delete-orphan",
        order_by=(
            "CurriculumPathLesson.display_order, "
            "CurriculumPathLesson.lesson_id"
        ),
    )
    lessons: Mapped[list[Lesson]] = relationship(
        "Lesson",
        secondary="curriculum_path_lessons",
        back_populates="curriculum_paths",
        order_by=(
            "CurriculumPathLesson.display_order, "
            "CurriculumPathLesson.lesson_id"
        ),
        viewonly=True,
    )


class CurriculumPathLesson(Base):
    __tablename__ = "curriculum_path_lessons"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_path_id",
            "lesson_id",
            name="uq_curriculum_path_lesson_pair",
        ),
        UniqueConstraint(
            "curriculum_path_id",
            "display_order",
            name="uq_curriculum_path_lesson_order",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="ck_curriculum_path_lessons_display_order_nonnegative",
        ),
    )

    curriculum_path_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_paths.id", ondelete="CASCADE"),
        primary_key=True,
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    curriculum_path: Mapped[CurriculumPath] = relationship(
        "CurriculumPath",
        back_populates="lesson_links",
    )
    lesson: Mapped[Lesson] = relationship(
        "Lesson",
        back_populates="curriculum_path_links",
    )
