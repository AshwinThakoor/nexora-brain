from enum import Enum


class StringEnum(str, Enum):
    """Enum whose values persist cleanly in portable VARCHAR columns."""

    def __str__(self) -> str:
        return self.value


class KnowledgeLifecycleStatus(StringEnum):
    DRAFT = "draft"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class ReviewStatus(StringEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class DifficultyLevel(StringEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    PROFESSIONAL = "professional"


class ClaimType(StringEnum):
    ESTABLISHED_FACT = "established_fact"
    DEFINITION = "definition"
    INTERPRETATION = "interpretation"
    EXPERT_OPINION = "expert_opinion"
    STRATEGY_RULE = "strategy_rule"
    STATISTICAL_OBSERVATION = "statistical_observation"
    BACKTEST_RESULT = "backtest_result"
    LIVE_RESULT = "live_result"
    MODEL_OUTPUT = "model_output"
    HYPOTHESIS = "hypothesis"


class KnowledgeSectionType(StringEnum):
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    HISTORY = "history"
    FORMULA = "formula"
    EXAMPLE = "example"
    COUNTER_EXAMPLE = "counter_example"
    TRADING_APPLICATION = "trading_application"
    RISK = "risk"
    LIMITATION = "limitation"
    COMMON_MISTAKE = "common_mistake"
    CASE_STUDY = "case_study"
    CHECKLIST = "checklist"
    FAQ = "faq"
    IMPLEMENTATION_NOTE = "implementation_note"
    MARKET_BEHAVIOR = "market_behavior"
    OTHER = "other"


class LearnerStatus(StringEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class EnrollmentStatus(StringEnum):
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LessonProgressStatus(StringEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class AssessmentType(StringEnum):
    QUIZ = "quiz"
    EXAM = "exam"
    PRACTICE = "practice"


class QuestionType(StringEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class AttemptStatus(StringEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class CompletionSource(StringEnum):
    MANUAL = "manual"
    PROGRESS = "progress"
    ASSESSMENT = "assessment"
    IMPORT = "import"
    SYSTEM = "system"


class AcademyRole(StringEnum):
    LEARNER = "learner"
    INSTRUCTOR = "instructor"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class SourceType(StringEnum):
    BOOK = "book"
    RESEARCH_PAPER = "research_paper"
    WEBSITE = "website"
    API = "api"
    GOVERNMENT_REPORT = "government_report"
    SEC_FILING = "sec_filing"
    USER_UPLOAD = "user_upload"
    INTERNAL_NOTE = "internal_note"
    COURSE = "course"
    ARTICLE = "article"
    OTHER = "other"


class TrustLevel(StringEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    OFFICIAL = "official"


class DocumentStatus(StringEnum):
    DRAFT = "draft"
    REGISTERED = "registered"
    READY = "ready"
    PROCESSING = "processing"
    PROCESSED = "processed"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DocumentType(StringEnum):
    BOOK = "book"
    REPORT = "report"
    ARTICLE = "article"
    WHITEPAPER = "whitepaper"
    SEC_FILING = "sec_filing"
    REGULATION = "regulation"
    RESEARCH = "research"
    NOTE = "note"
    COURSE = "course"
    OTHER = "other"


class ProcessingStatus(StringEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    COMPLETE = "complete"


class RelationshipType(StringEnum):
    SUPERSEDES = "supersedes"
    REPLACES = "replaces"
    TRANSLATION = "translation"
    COMPANION = "companion"
    REFERENCES = "references"
    DERIVED_FROM = "derived_from"


class JobStatus(StringEnum):
    NEW = "new"
    QUEUED = "queued"
    RESERVED = "reserved"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class AuditEventType(StringEnum):
    CREATED = "created"
    QUEUED = "queued"
    RESERVED = "reserved"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRIED = "retried"
    CANCELLED = "cancelled"
    RELEASED = "released"


class UploadStatus(StringEnum):
    CREATED = "created"
    RECEIVING = "receiving"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class StorageProviderType(StringEnum):
    LOCAL = "local"
    NULL = "null"
    S3 = "s3"
    AZURE = "azure"
    GCS = "gcs"
    MINIO = "minio"


class HashAlgorithm(StringEnum):
    SHA256 = "sha256"
    SHA1 = "sha1"
    MD5 = "md5"


class ParseResultStatus(StringEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    PARSING = "parsing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class ParseExecutionStatus(StringEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ParseArtifactType(StringEnum):
    CANONICAL_MANIFEST = "canonical_manifest"
    METADATA = "metadata"
    STATISTICS = "statistics"
    WARNING = "warning"
    VALIDATION_REPORT = "validation_report"


class ChunkSetStatus(StringEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    CHUNKING = "chunking"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class ChunkingExecutionStatus(StringEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ChunkContentType(StringEnum):
    TEXT = "text"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    LIST = "list"
    BLOCKQUOTE = "blockquote"
    CODE = "code"
    TABLE = "table"
    MIXED = "mixed"


class ChunkRelationshipType(StringEnum):
    CONTINUES = "continues"
    OVERLAPS = "overlaps"
    SPLIT_FROM = "split_from"
    TABLE_CONTINUATION = "table_continuation"
    CODE_CONTINUATION = "code_continuation"
    SAME_SECTION = "same_section"


class ChunkingArtifactType(StringEnum):
    MANIFEST = "manifest"
    STATISTICS = "statistics"
    WARNING = "warning"
    VALIDATION_REPORT = "validation_report"
    CONFIGURATION = "configuration"


class GradingStatus(StringEnum):
    PENDING = "pending"
    AUTOMATIC_GRADED = "automatic_graded"
    MANUAL_GRADING_REQUIRED = "manual_grading_required"
    GRADED = "graded"
    REVIEW_PENDING = "review_pending"
    CHANGES_REQUESTED = "changes_requested"
    FINAL = "final"
    REGRADED = "regraded"


class AssessmentReviewStatus(StringEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REGRADED = "regraded"


class GradingAuditEventType(StringEnum):
    MANUAL_GRADE_CREATED = "manual_grade_created"
    GRADE_CHANGED = "grade_changed"
    ATTEMPT_RECALCULATED = "attempt_recalculated"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_APPROVED = "review_approved"
    REVIEW_CHANGES_REQUESTED = "review_changes_requested"
    ATTEMPT_REGRADED = "attempt_regraded"


__all__ = [
    "AcademyRole",
    "AssessmentReviewStatus",
    "AssessmentType",
    "AttemptStatus",
    "AuditEventType",
    "ClaimType",
    "ChunkContentType",
    "ChunkRelationshipType",
    "ChunkSetStatus",
    "ChunkingArtifactType",
    "ChunkingExecutionStatus",
    "CompletionSource",
    "DifficultyLevel",
    "DocumentStatus",
    "DocumentType",
    "EnrollmentStatus",
    "GradingAuditEventType",
    "GradingStatus",
    "HashAlgorithm",
    "KnowledgeLifecycleStatus",
    "KnowledgeSectionType",
    "JobStatus",
    "LearnerStatus",
    "LessonProgressStatus",
    "ParseArtifactType",
    "ParseExecutionStatus",
    "ParseResultStatus",
    "QuestionType",
    "ProcessingStatus",
    "RelationshipType",
    "ReviewStatus",
    "SourceType",
    "StorageProviderType",
    "StringEnum",
    "TrustLevel",
    "UploadStatus",
]
