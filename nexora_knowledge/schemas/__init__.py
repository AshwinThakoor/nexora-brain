from pathlib import Path
from pydantic import BaseModel, Field, field_validator

LICENSES = {"UNKNOWN","PUBLIC_DOMAIN","OPEN_LICENSE","OWNED","PRIVATE_REFERENCE","RESTRICTED"}

class IngestRequest(BaseModel):
    file_path: str
    title: str | None = None
    author: str | None = None
    publisher: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    license_status: str = "UNKNOWN"
    license_notes: str | None = None
    commercial_use_allowed: bool = False
    quality_score: int = Field(default=50, ge=0, le=100)

    @field_validator("license_status")
    @classmethod
    def validate_license(cls, value: str) -> str:
        value = value.upper()
        if value not in LICENSES:
            raise ValueError("Invalid license status")
        return value

    @field_validator("file_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = Path(value)
        if not path.exists() or not path.is_file():
            raise ValueError(f"File does not exist: {value}")
        return str(path)

class SearchResult(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    category: str
    chunk_index: int
    content: str
    score: int
