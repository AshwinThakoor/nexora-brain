from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .common import TimestampMixin
from .enums import KnowledgeLifecycleStatus, ReviewStatus


JsonValue = dict[str, Any] | list[Any]


class AssetClass(TimestampMixin, Base):
    __tablename__ = "asset_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    market_structure: Mapped[str] = mapped_column(Text, nullable=False)
    typical_participants: Mapped[str] = mapped_column(Text, nullable=False)
    risk_profile: Mapped[str] = mapped_column(Text, nullable=False)
    trading_hours_notes: Mapped[str] = mapped_column(Text, nullable=False)

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="asset_class",
    )
    instruments: Mapped[list["Instrument"]] = relationship(
        "Instrument",
        back_populates="asset_class",
    )


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint(
            "canonical_symbol",
            "venue",
            name="uq_instrument_symbol_venue",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    asset_class_id: Mapped[int] = mapped_column(
        ForeignKey("asset_classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    canonical_symbol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    base_asset: Mapped[str | None] = mapped_column(String(100))
    quote_asset: Mapped[str | None] = mapped_column(String(100))
    instrument_type: Mapped[str] = mapped_column(String(100), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(255))
    contract_type: Mapped[str | None] = mapped_column(String(100))
    contract_size: Mapped[float | None] = mapped_column(Float)
    tick_size: Mapped[float | None] = mapped_column(Float)
    tick_value: Mapped[float | None] = mapped_column(Float)
    price_precision: Mapped[int | None] = mapped_column(Integer)
    volume_min: Mapped[float | None] = mapped_column(Float)
    volume_max: Mapped[float | None] = mapped_column(Float)
    volume_step: Mapped[float | None] = mapped_column(Float)
    trading_hours: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str | None] = mapped_column(String(100))
    settlement_type: Mapped[str | None] = mapped_column(String(100))
    expiry_behavior: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    metadata_json: Mapped[JsonValue | None] = mapped_column(JSON)

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="instrument",
    )
    asset_class: Mapped[AssetClass] = relationship(
        "AssetClass",
        back_populates="instruments",
    )
    case_studies: Mapped[list["CaseStudy"]] = relationship(
        "CaseStudy",
        back_populates="instrument",
    )


class Indicator(TimestampMixin, Base):
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(100))
    indicator_family: Mapped[str] = mapped_column(String(100), nullable=False)
    formula_text: Mapped[str | None] = mapped_column(Text)
    calculation_method: Mapped[str] = mapped_column(Text, nullable=False)
    default_parameters_json: Mapped[JsonValue | None] = mapped_column(JSON)
    input_requirements_json: Mapped[JsonValue | None] = mapped_column(JSON)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    bullish_signals: Mapped[str | None] = mapped_column(Text)
    bearish_signals: Mapped[str | None] = mapped_column(Text)
    suitable_regimes: Mapped[str | None] = mapped_column(Text)
    unsuitable_regimes: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)
    common_misuse: Mapped[str | None] = mapped_column(Text)
    implementation_notes: Mapped[str | None] = mapped_column(Text)

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="indicator",
    )


class Strategy(TimestampMixin, Base):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_family: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=KnowledgeLifecycleStatus.DRAFT.value,
    )
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ReviewStatus.PENDING.value,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    eligible_markets_json: Mapped[JsonValue | None] = mapped_column(JSON)
    eligible_instruments_json: Mapped[JsonValue | None] = mapped_column(JSON)
    timeframes_json: Mapped[JsonValue | None] = mapped_column(JSON)
    required_data_json: Mapped[JsonValue | None] = mapped_column(JSON)
    market_regimes_json: Mapped[JsonValue | None] = mapped_column(JSON)
    entry_rules_json: Mapped[JsonValue] = mapped_column(JSON, nullable=False)
    exit_rules_json: Mapped[JsonValue] = mapped_column(JSON, nullable=False)
    invalidation_rules_json: Mapped[JsonValue] = mapped_column(
        JSON,
        nullable=False,
    )
    risk_rules_json: Mapped[JsonValue] = mapped_column(JSON, nullable=False)
    filters_json: Mapped[JsonValue | None] = mapped_column(JSON)
    parameter_schema_json: Mapped[JsonValue | None] = mapped_column(JSON)
    known_weaknesses: Mapped[str | None] = mapped_column(Text)

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="strategy",
    )
    case_studies: Mapped[list["CaseStudy"]] = relationship(
        "CaseStudy",
        back_populates="strategy",
    )


class Pattern(TimestampMixin, Base):
    __tablename__ = "patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern_family: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detection_rules_json: Mapped[JsonValue] = mapped_column(JSON, nullable=False)
    confirmation_rules_json: Mapped[JsonValue | None] = mapped_column(JSON)
    invalidation_rules_json: Mapped[JsonValue | None] = mapped_column(JSON)
    suitable_regimes_json: Mapped[JsonValue | None] = mapped_column(JSON)
    failure_modes: Mapped[str | None] = mapped_column(Text)
    visual_description: Mapped[str | None] = mapped_column(Text)

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="pattern",
    )


class EconomicEventType(TimestampMixin, Base):
    __tablename__ = "economic_event_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_or_region: Mapped[str | None] = mapped_column(String(255))
    frequency: Mapped[str | None] = mapped_column(String(100))
    release_authority: Mapped[str | None] = mapped_column(String(255))
    affected_assets_json: Mapped[JsonValue | None] = mapped_column(JSON)
    interpretation_rules: Mapped[str | None] = mapped_column(Text)
    typical_volatility_effect: Mapped[str | None] = mapped_column(Text)
    pre_event_risk_policy: Mapped[str | None] = mapped_column(Text)
    post_event_risk_policy: Mapped[str | None] = mapped_column(Text)

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="economic_event_type",
    )


class Formula(TimestampMixin, Base):
    __tablename__ = "formulas"
    __table_args__ = (
        UniqueConstraint("concept_id", "name", name="uq_formula_concept_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    latex_expression: Mapped[str | None] = mapped_column(Text)
    variables_json: Mapped[JsonValue | None] = mapped_column(JSON)
    assumptions: Mapped[str | None] = mapped_column(Text)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    worked_example: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)

    concept: Mapped["Concept"] = relationship(
        "Concept",
        back_populates="formulas",
    )


class CaseStudy(TimestampMixin, Base):
    __tablename__ = "case_studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    market_regime: Mapped[str | None] = mapped_column(String(100))
    context: Mapped[str] = mapped_column(Text, nullable=False)
    available_information: Mapped[str | None] = mapped_column(Text)
    decision_options: Mapped[str | None] = mapped_column(Text)
    chosen_decision: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    lessons: Mapped[str] = mapped_column(Text, nullable=False)
    data_snapshot_reference: Mapped[str | None] = mapped_column(String(1000))
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ReviewStatus.PENDING.value,
    )

    concept: Mapped["Concept | None"] = relationship(
        "Concept",
        back_populates="case_studies",
    )
    instrument: Mapped[Instrument | None] = relationship(
        "Instrument",
        back_populates="case_studies",
    )
    strategy: Mapped[Strategy | None] = relationship(
        "Strategy",
        back_populates="case_studies",
    )
