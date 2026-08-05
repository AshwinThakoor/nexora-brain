from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ParserCapabilityRead(BaseModel):
    name: str
    version: str
    extensions: tuple[str, ...]
    mime_types: tuple[str, ...]
    implemented: bool

    model_config = ConfigDict(from_attributes=True)


class ParserValidationResponse(BaseModel):
    valid: bool
    filename: str
    parser_name: str
    parser_version: str
    implemented: bool


__all__ = ["ParserCapabilityRead", "ParserValidationResponse"]
