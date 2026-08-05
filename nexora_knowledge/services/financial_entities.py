from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    AssetClass,
    CaseStudy,
    Concept,
    EconomicEventType,
    Formula,
    Indicator,
    Instrument,
    Pattern,
    Strategy,
)
from ..models.enums import KnowledgeLifecycleStatus, ReviewStatus
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


ModelT = TypeVar("ModelT")
JsonValue = dict[str, Any] | list[Any]

JSON_FIELDS: dict[type, set[str]] = {
    Instrument: {"metadata_json"},
    Indicator: {"default_parameters_json", "input_requirements_json"},
    Strategy: {
        "eligible_markets_json",
        "eligible_instruments_json",
        "timeframes_json",
        "required_data_json",
        "market_regimes_json",
        "entry_rules_json",
        "exit_rules_json",
        "invalidation_rules_json",
        "risk_rules_json",
        "filters_json",
        "parameter_schema_json",
    },
    Pattern: {
        "detection_rules_json",
        "confirmation_rules_json",
        "invalidation_rules_json",
        "suitable_regimes_json",
    },
    EconomicEventType: {"affected_assets_json"},
    Formula: {"variables_json"},
}

REQUIRED_JSON_FIELDS: dict[type, set[str]] = {
    Strategy: {
        "entry_rules_json",
        "exit_rules_json",
        "invalidation_rules_json",
        "risk_rules_json",
    },
    Pattern: {"detection_rules_json"},
}

ONE_TO_ONE_CONCEPT_MODELS = {
    AssetClass,
    Instrument,
    Indicator,
    Strategy,
    Pattern,
    EconomicEventType,
}


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value)


def _validate_enum(field: str, value: Any, enum_type: type) -> None:
    if value is None:
        return
    allowed = {member.value for member in enum_type}
    if _enum_value(value) not in allowed:
        raise ResourceValidationError(
            f"{field} must be one of: {', '.join(sorted(allowed))}"
        )


def _require(db: Session, model: type[ModelT], item_id: int | None) -> ModelT | None:
    if item_id is None:
        return None
    item = db.get(model, item_id)
    if item is None:
        raise ResourceNotFoundError(model.__name__, item_id)
    return item


def _validate_json(model: type, data: Mapping[str, Any], *, creating: bool) -> None:
    for field in JSON_FIELDS.get(model, set()):
        if field not in data:
            continue
        value = data[field]
        if value is not None and not isinstance(value, (dict, list)):
            raise ResourceValidationError(
                f"{field} must be a JSON object or array"
            )
    if creating:
        for field in REQUIRED_JSON_FIELDS.get(model, set()):
            if field not in data or data[field] is None:
                raise ResourceValidationError(f"{field} is required")


def _validate_references(
    db: Session,
    model: type,
    data: Mapping[str, Any],
) -> None:
    if "concept_id" in data and data["concept_id"] is not None:
        _require(db, Concept, data["concept_id"])
    if model is Instrument and "asset_class_id" in data:
        _require(db, AssetClass, data["asset_class_id"])
    if model is CaseStudy:
        if "instrument_id" in data:
            _require(db, Instrument, data["instrument_id"])
        if "strategy_id" in data:
            _require(db, Strategy, data["strategy_id"])


def _validate_values(model: type, data: dict[str, Any], *, creating: bool) -> None:
    _validate_json(model, data, creating=creating)
    if model is Instrument:
        if "canonical_symbol" in data:
            data["canonical_symbol"] = data["canonical_symbol"].upper()
        nonnegative = (
            "contract_size",
            "tick_size",
            "tick_value",
            "price_precision",
            "volume_min",
            "volume_max",
            "volume_step",
        )
        for field in nonnegative:
            value = data.get(field)
            if value is not None and value < 0:
                raise ResourceValidationError(f"{field} cannot be negative")
        if (
            data.get("volume_min") is not None
            and data.get("volume_max") is not None
            and data["volume_min"] > data["volume_max"]
        ):
            raise ResourceValidationError(
                "volume_min cannot exceed volume_max"
            )
    if model is Strategy:
        version = data.get("version")
        if version is not None and version < 1:
            raise ResourceValidationError("version must be at least 1")
        _validate_enum(
            "lifecycle_status",
            data.get("lifecycle_status"),
            KnowledgeLifecycleStatus,
        )
        _validate_enum("review_status", data.get("review_status"), ReviewStatus)
    if model is CaseStudy:
        _validate_enum("review_status", data.get("review_status"), ReviewStatus)


def _ensure_unique(
    db: Session,
    model: type,
    data: Mapping[str, Any],
    *,
    exclude_id: int | None = None,
) -> None:
    if model in ONE_TO_ONE_CONCEPT_MODELS and data.get("concept_id") is not None:
        statement = select(model.id).where(model.concept_id == data["concept_id"])
        if exclude_id is not None:
            statement = statement.where(model.id != exclude_id)
        if db.scalar(statement) is not None:
            raise ResourceConflictError(
                f"{model.__name__} already exists for this Concept"
            )
    if model is Formula and {
        "concept_id",
        "name",
    } <= data.keys():
        statement = select(Formula.id).where(
            Formula.concept_id == data["concept_id"],
            Formula.name == data["name"],
        )
        if exclude_id is not None:
            statement = statement.where(Formula.id != exclude_id)
        if db.scalar(statement) is not None:
            raise ResourceConflictError("Formula already exists for this Concept")
    if model is Instrument and data.get("canonical_symbol"):
        statement = select(Instrument.id).where(
            Instrument.canonical_symbol == data["canonical_symbol"],
            Instrument.venue == data.get("venue"),
        )
        if exclude_id is not None:
            statement = statement.where(Instrument.id != exclude_id)
        if db.scalar(statement) is not None:
            raise ResourceConflictError(
                "Instrument symbol already exists for this venue"
            )


def _save(
    db: Session,
    *,
    message: str,
    commit: bool,
) -> None:
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(message) from exc


def _create(
    db: Session,
    model: type[ModelT],
    values: Mapping[str, Any],
    *,
    commit: bool,
) -> ModelT:
    data = dict(values)
    _validate_references(db, model, data)
    _validate_values(model, data, creating=True)
    _ensure_unique(db, model, data)
    item = model(**data)
    db.add(item)
    _save(
        db,
        message=f"{model.__name__} could not be created",
        commit=commit,
    )
    return item


def _get(db: Session, model: type[ModelT], item_id: int) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise ResourceNotFoundError(model.__name__, item_id)
    return item


def _update(
    db: Session,
    model: type[ModelT],
    item_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool,
) -> ModelT:
    item = _get(db, model, item_id)
    data = dict(values)
    if not data:
        return item
    _validate_references(db, model, data)
    _validate_values(model, data, creating=False)
    candidate = {
        column.name: getattr(item, column.name)
        for column in model.__table__.columns
    }
    candidate.update(data)
    _ensure_unique(db, model, candidate, exclude_id=item_id)
    for field, value in data.items():
        setattr(item, field, value)
    _save(
        db,
        message=f"{model.__name__} could not be updated",
        commit=commit,
    )
    return item


def _delete(
    db: Session,
    model: type[ModelT],
    item_id: int,
    *,
    commit: bool,
) -> None:
    db.delete(_get(db, model, item_id))
    _save(
        db,
        message=f"{model.__name__} could not be deleted",
        commit=commit,
    )


def create_asset_class(db, values, *, commit=True):
    return _create(db, AssetClass, values, commit=commit)


def get_asset_class(db, item_id):
    return _get(db, AssetClass, item_id)


def update_asset_class(db, item_id, values, *, commit=True):
    return _update(db, AssetClass, item_id, values, commit=commit)


def delete_asset_class(db, item_id, *, commit=True):
    return _delete(db, AssetClass, item_id, commit=commit)


def create_instrument(db, values, *, commit=True):
    return _create(db, Instrument, values, commit=commit)


def get_instrument(db, item_id):
    return _get(db, Instrument, item_id)


def update_instrument(db, item_id, values, *, commit=True):
    return _update(db, Instrument, item_id, values, commit=commit)


def delete_instrument(db, item_id, *, commit=True):
    return _delete(db, Instrument, item_id, commit=commit)


def create_indicator(db, values, *, commit=True):
    return _create(db, Indicator, values, commit=commit)


def get_indicator(db, item_id):
    return _get(db, Indicator, item_id)


def update_indicator(db, item_id, values, *, commit=True):
    return _update(db, Indicator, item_id, values, commit=commit)


def delete_indicator(db, item_id, *, commit=True):
    return _delete(db, Indicator, item_id, commit=commit)


def create_strategy(db, values, *, commit=True):
    return _create(db, Strategy, values, commit=commit)


def get_strategy(db, item_id):
    return _get(db, Strategy, item_id)


def update_strategy(db, item_id, values, *, commit=True):
    return _update(db, Strategy, item_id, values, commit=commit)


def delete_strategy(db, item_id, *, commit=True):
    return _delete(db, Strategy, item_id, commit=commit)


def create_pattern(db, values, *, commit=True):
    return _create(db, Pattern, values, commit=commit)


def get_pattern(db, item_id):
    return _get(db, Pattern, item_id)


def update_pattern(db, item_id, values, *, commit=True):
    return _update(db, Pattern, item_id, values, commit=commit)


def delete_pattern(db, item_id, *, commit=True):
    return _delete(db, Pattern, item_id, commit=commit)


def create_economic_event_type(db, values, *, commit=True):
    return _create(db, EconomicEventType, values, commit=commit)


def get_economic_event_type(db, item_id):
    return _get(db, EconomicEventType, item_id)


def update_economic_event_type(db, item_id, values, *, commit=True):
    return _update(db, EconomicEventType, item_id, values, commit=commit)


def delete_economic_event_type(db, item_id, *, commit=True):
    return _delete(db, EconomicEventType, item_id, commit=commit)


def create_formula(db, values, *, commit=True):
    return _create(db, Formula, values, commit=commit)


def get_formula(db, item_id):
    return _get(db, Formula, item_id)


def update_formula(db, item_id, values, *, commit=True):
    return _update(db, Formula, item_id, values, commit=commit)


def delete_formula(db, item_id, *, commit=True):
    return _delete(db, Formula, item_id, commit=commit)


def create_case_study(db, values, *, commit=True):
    return _create(db, CaseStudy, values, commit=commit)


def get_case_study(db, item_id):
    return _get(db, CaseStudy, item_id)


def update_case_study(db, item_id, values, *, commit=True):
    return _update(db, CaseStudy, item_id, values, commit=commit)


def delete_case_study(db, item_id, *, commit=True):
    return _delete(db, CaseStudy, item_id, commit=commit)
