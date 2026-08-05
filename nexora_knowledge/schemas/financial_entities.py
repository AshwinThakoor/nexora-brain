from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar

from pydantic import Field

from ..models.enums import KnowledgeLifecycleStatus, ReviewStatus
from .common import (
    NameString,
    ORMResponse,
    PartialUpdateModel,
    PositiveId,
    RequiredText,
    TitleString,
    TypeString,
)


JsonValue = dict[str, Any] | list[Any]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class AssetClassBase(ORMResponse):
    concept_id: PositiveId
    name: NameString
    description: RequiredText
    market_structure: RequiredText
    typical_participants: RequiredText
    risk_profile: RequiredText
    trading_hours_notes: RequiredText


class AssetClassCreate(AssetClassBase):
    pass


class AssetClassUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        AssetClassBase.model_fields
    )

    concept_id: PositiveId | None = None
    name: NameString | None = None
    description: RequiredText | None = None
    market_structure: RequiredText | None = None
    typical_participants: RequiredText | None = None
    risk_profile: RequiredText | None = None
    trading_hours_notes: RequiredText | None = None


class AssetClassRead(AssetClassBase):
    id: int
    created_at: datetime
    updated_at: datetime


class InstrumentBase(ORMResponse):
    concept_id: PositiveId
    asset_class_id: PositiveId
    canonical_symbol: TypeString
    display_name: TitleString
    base_asset: TypeString | None = None
    quote_asset: TypeString | None = None
    instrument_type: TypeString
    venue: NameString | None = None
    contract_type: TypeString | None = None
    contract_size: NonNegativeFloat | None = None
    tick_size: NonNegativeFloat | None = None
    tick_value: NonNegativeFloat | None = None
    price_precision: NonNegativeInt | None = None
    volume_min: NonNegativeFloat | None = None
    volume_max: NonNegativeFloat | None = None
    volume_step: NonNegativeFloat | None = None
    trading_hours: str | None = None
    timezone: TypeString | None = None
    settlement_type: TypeString | None = None
    expiry_behavior: str | None = None
    is_active: bool = True
    metadata_json: JsonValue | None = None


class InstrumentCreate(InstrumentBase):
    pass


class InstrumentUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "concept_id",
            "asset_class_id",
            "canonical_symbol",
            "display_name",
            "instrument_type",
            "is_active",
        }
    )

    concept_id: PositiveId | None = None
    asset_class_id: PositiveId | None = None
    canonical_symbol: TypeString | None = None
    display_name: TitleString | None = None
    base_asset: TypeString | None = None
    quote_asset: TypeString | None = None
    instrument_type: TypeString | None = None
    venue: NameString | None = None
    contract_type: TypeString | None = None
    contract_size: NonNegativeFloat | None = None
    tick_size: NonNegativeFloat | None = None
    tick_value: NonNegativeFloat | None = None
    price_precision: NonNegativeInt | None = None
    volume_min: NonNegativeFloat | None = None
    volume_max: NonNegativeFloat | None = None
    volume_step: NonNegativeFloat | None = None
    trading_hours: str | None = None
    timezone: TypeString | None = None
    settlement_type: TypeString | None = None
    expiry_behavior: str | None = None
    is_active: bool | None = None
    metadata_json: JsonValue | None = None


class InstrumentRead(InstrumentBase):
    id: int
    created_at: datetime
    updated_at: datetime


class IndicatorBase(ORMResponse):
    concept_id: PositiveId
    name: NameString
    abbreviation: TypeString | None = None
    indicator_family: TypeString
    formula_text: str | None = None
    calculation_method: RequiredText
    default_parameters_json: JsonValue | None = None
    input_requirements_json: JsonValue | None = None
    interpretation: RequiredText
    bullish_signals: str | None = None
    bearish_signals: str | None = None
    suitable_regimes: str | None = None
    unsuitable_regimes: str | None = None
    strengths: str | None = None
    limitations: str | None = None
    common_misuse: str | None = None
    implementation_notes: str | None = None


class IndicatorCreate(IndicatorBase):
    pass


class IndicatorUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "concept_id",
            "name",
            "indicator_family",
            "calculation_method",
            "interpretation",
        }
    )

    concept_id: PositiveId | None = None
    name: NameString | None = None
    abbreviation: TypeString | None = None
    indicator_family: TypeString | None = None
    formula_text: str | None = None
    calculation_method: RequiredText | None = None
    default_parameters_json: JsonValue | None = None
    input_requirements_json: JsonValue | None = None
    interpretation: RequiredText | None = None
    bullish_signals: str | None = None
    bearish_signals: str | None = None
    suitable_regimes: str | None = None
    unsuitable_regimes: str | None = None
    strengths: str | None = None
    limitations: str | None = None
    common_misuse: str | None = None
    implementation_notes: str | None = None


class IndicatorRead(IndicatorBase):
    id: int
    created_at: datetime
    updated_at: datetime


class StrategyBase(ORMResponse):
    concept_id: PositiveId
    name: NameString
    strategy_family: TypeString
    description: RequiredText
    lifecycle_status: KnowledgeLifecycleStatus = KnowledgeLifecycleStatus.DRAFT
    review_status: ReviewStatus = ReviewStatus.PENDING
    version: int = Field(default=1, ge=1)
    eligible_markets_json: JsonValue | None = None
    eligible_instruments_json: JsonValue | None = None
    timeframes_json: JsonValue | None = None
    required_data_json: JsonValue | None = None
    market_regimes_json: JsonValue | None = None
    entry_rules_json: JsonValue
    exit_rules_json: JsonValue
    invalidation_rules_json: JsonValue
    risk_rules_json: JsonValue
    filters_json: JsonValue | None = None
    parameter_schema_json: JsonValue | None = None
    known_weaknesses: str | None = None


class StrategyCreate(StrategyBase):
    pass


class StrategyUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "concept_id",
            "name",
            "strategy_family",
            "description",
            "lifecycle_status",
            "review_status",
            "version",
            "entry_rules_json",
            "exit_rules_json",
            "invalidation_rules_json",
            "risk_rules_json",
        }
    )

    concept_id: PositiveId | None = None
    name: NameString | None = None
    strategy_family: TypeString | None = None
    description: RequiredText | None = None
    lifecycle_status: KnowledgeLifecycleStatus | None = None
    review_status: ReviewStatus | None = None
    version: int | None = Field(default=None, ge=1)
    eligible_markets_json: JsonValue | None = None
    eligible_instruments_json: JsonValue | None = None
    timeframes_json: JsonValue | None = None
    required_data_json: JsonValue | None = None
    market_regimes_json: JsonValue | None = None
    entry_rules_json: JsonValue | None = None
    exit_rules_json: JsonValue | None = None
    invalidation_rules_json: JsonValue | None = None
    risk_rules_json: JsonValue | None = None
    filters_json: JsonValue | None = None
    parameter_schema_json: JsonValue | None = None
    known_weaknesses: str | None = None


class StrategyRead(StrategyBase):
    id: int
    created_at: datetime
    updated_at: datetime


class PatternBase(ORMResponse):
    concept_id: PositiveId
    name: NameString
    pattern_family: TypeString
    description: RequiredText
    detection_rules_json: JsonValue
    confirmation_rules_json: JsonValue | None = None
    invalidation_rules_json: JsonValue | None = None
    suitable_regimes_json: JsonValue | None = None
    failure_modes: str | None = None
    visual_description: str | None = None


class PatternCreate(PatternBase):
    pass


class PatternUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "concept_id",
            "name",
            "pattern_family",
            "description",
            "detection_rules_json",
        }
    )

    concept_id: PositiveId | None = None
    name: NameString | None = None
    pattern_family: TypeString | None = None
    description: RequiredText | None = None
    detection_rules_json: JsonValue | None = None
    confirmation_rules_json: JsonValue | None = None
    invalidation_rules_json: JsonValue | None = None
    suitable_regimes_json: JsonValue | None = None
    failure_modes: str | None = None
    visual_description: str | None = None


class PatternRead(PatternBase):
    id: int
    created_at: datetime
    updated_at: datetime


class EconomicEventTypeBase(ORMResponse):
    concept_id: PositiveId
    name: NameString
    country_or_region: NameString | None = None
    frequency: TypeString | None = None
    release_authority: NameString | None = None
    affected_assets_json: JsonValue | None = None
    interpretation_rules: str | None = None
    typical_volatility_effect: str | None = None
    pre_event_risk_policy: str | None = None
    post_event_risk_policy: str | None = None


class EconomicEventTypeCreate(EconomicEventTypeBase):
    pass


class EconomicEventTypeUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"concept_id", "name"}
    )

    concept_id: PositiveId | None = None
    name: NameString | None = None
    country_or_region: NameString | None = None
    frequency: TypeString | None = None
    release_authority: NameString | None = None
    affected_assets_json: JsonValue | None = None
    interpretation_rules: str | None = None
    typical_volatility_effect: str | None = None
    pre_event_risk_policy: str | None = None
    post_event_risk_policy: str | None = None


class EconomicEventTypeRead(EconomicEventTypeBase):
    id: int
    created_at: datetime
    updated_at: datetime


class FormulaBase(ORMResponse):
    concept_id: PositiveId
    name: NameString
    expression: RequiredText
    latex_expression: str | None = None
    variables_json: JsonValue | None = None
    assumptions: str | None = None
    interpretation: RequiredText
    worked_example: str | None = None
    limitations: str | None = None


class FormulaCreate(FormulaBase):
    pass


class FormulaUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"concept_id", "name", "expression", "interpretation"}
    )

    concept_id: PositiveId | None = None
    name: NameString | None = None
    expression: RequiredText | None = None
    latex_expression: str | None = None
    variables_json: JsonValue | None = None
    assumptions: str | None = None
    interpretation: RequiredText | None = None
    worked_example: str | None = None
    limitations: str | None = None


class FormulaRead(FormulaBase):
    id: int
    created_at: datetime
    updated_at: datetime


class CaseStudyBase(ORMResponse):
    concept_id: PositiveId | None = None
    title: TitleString
    instrument_id: PositiveId | None = None
    strategy_id: PositiveId | None = None
    event_date: datetime | None = None
    market_regime: TypeString | None = None
    context: RequiredText
    available_information: str | None = None
    decision_options: str | None = None
    chosen_decision: str | None = None
    outcome: str | None = None
    lessons: RequiredText
    data_snapshot_reference: str | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING


class CaseStudyCreate(CaseStudyBase):
    pass


class CaseStudyUpdate(PartialUpdateModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"title", "context", "lessons", "review_status"}
    )

    concept_id: PositiveId | None = None
    title: TitleString | None = None
    instrument_id: PositiveId | None = None
    strategy_id: PositiveId | None = None
    event_date: datetime | None = None
    market_regime: TypeString | None = None
    context: RequiredText | None = None
    available_information: str | None = None
    decision_options: str | None = None
    chosen_decision: str | None = None
    outcome: str | None = None
    lessons: RequiredText | None = None
    data_snapshot_reference: str | None = None
    review_status: ReviewStatus | None = None


class CaseStudyRead(CaseStudyBase):
    id: int
    created_at: datetime
    updated_at: datetime


AssetClassResponse = AssetClassRead
InstrumentResponse = InstrumentRead
IndicatorResponse = IndicatorRead
StrategyResponse = StrategyRead
PatternResponse = PatternRead
EconomicEventTypeResponse = EconomicEventTypeRead
FormulaResponse = FormulaRead
CaseStudyResponse = CaseStudyRead


__all__ = [
    name
    for name, value in globals().items()
    if (
        isinstance(value, type)
        and value.__module__ == __name__
        and name.endswith(("Base", "Create", "Update", "Read", "Response"))
    )
]
