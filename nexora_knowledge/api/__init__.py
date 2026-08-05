from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..database import init_database  # Backward-compatible module attribute.
from ..services import (
    AcademyInputError,
    AuthenticationRequiredError,
    AuthorizationDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)
from ..parsers import ParserError
from .academy_admin import router as academy_admin_router
from .academy_catalog import router as academy_catalog_router
from .academy_grading import router as academy_grading_router
from .academy_learning import router as academy_learning_router
from .categories import router as categories_router
from .claims import router as claims_router
from .chunks import (
    chunk_router,
    chunk_set_router,
    parse_result_router as chunk_parse_result_router,
)
from .concepts import router as concepts_router
from .dependencies import get_db
from .document_registry import (
    import_batch_router,
    router as document_registry_router,
)
from .evidence import router as evidence_router
from .legacy import health, ingest, router as legacy_router, search, stats
from .ingestion import (
    processing_node_router,
    router as ingestion_router,
)
from .relationships import router as relationships_router
from .parsers import router as parsers_router
from .parse_results import (
    file_router as parse_file_router,
    router as parse_results_router,
)
from .sources import router as sources_router
from .source_registry import router as source_registry_router
from .storage import file_router as storage_file_router, router as storage_router
from .tags import router as tags_router


def startup() -> None:
    """Run non-mutating API startup work.

    Database schemas are managed explicitly with Alembic before the API starts.
    """


@asynccontextmanager
async def lifespan(application: FastAPI):
    del application
    startup()
    yield


app = FastAPI(
    title="NEXORA Knowledge Engine",
    version="2.0.0",
    lifespan=lifespan,
)


@app.exception_handler(ResourceNotFoundError)
async def handle_not_found(
    request: Request,
    exc: ResourceNotFoundError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=404, content={"detail": exc.detail})


@app.exception_handler(ResourceConflictError)
async def handle_conflict(
    request: Request,
    exc: ResourceConflictError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=409, content={"detail": exc.detail})


@app.exception_handler(ResourceValidationError)
async def handle_validation(
    request: Request,
    exc: ResourceValidationError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=422, content={"detail": exc.detail})


@app.exception_handler(ParserError)
async def handle_parser_error(
    request: Request,
    exc: ParserError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(AcademyInputError)
async def handle_academy_input(
    request: Request,
    exc: AcademyInputError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=400, content={"detail": exc.detail})


@app.exception_handler(AuthenticationRequiredError)
async def handle_authentication(
    request: Request,
    exc: AuthenticationRequiredError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=401, content={"detail": exc.detail})


@app.exception_handler(AuthorizationDeniedError)
async def handle_authorization(
    request: Request,
    exc: AuthorizationDeniedError,
) -> JSONResponse:
    del request
    return JSONResponse(status_code=403, content={"detail": exc.detail})


app.include_router(legacy_router)
app.include_router(categories_router)
app.include_router(concepts_router)
app.include_router(sources_router)
app.include_router(source_registry_router)
app.include_router(document_registry_router)
app.include_router(import_batch_router)
app.include_router(ingestion_router)
app.include_router(processing_node_router)
app.include_router(storage_router)
app.include_router(storage_file_router)
app.include_router(parsers_router)
app.include_router(parse_file_router)
app.include_router(parse_results_router)
app.include_router(chunk_parse_result_router)
app.include_router(chunk_set_router)
app.include_router(chunk_router)
app.include_router(claims_router)
app.include_router(evidence_router)
app.include_router(relationships_router)
app.include_router(tags_router)
app.include_router(academy_catalog_router)
app.include_router(academy_learning_router)
app.include_router(academy_grading_router)
app.include_router(academy_admin_router)


__all__ = [
    "app",
    "get_db",
    "health",
    "ingest",
    "search",
    "startup",
    "stats",
]
