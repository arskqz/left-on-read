"""UI-free core: data model, schemas, file I/O and the project file. No Qt imports here."""

from .io import Dataset, DatasetLoadError, FileFormat, load, save
from .model import ARCHIVE, KEEP, ROLES, STATUSES, UNREVIEWED, Conversation, Issue, Message, validate
from .project import PROJECT_SUFFIX, Project, ProjectError, SourceState
from .schema import SCHEMAS, SchemaDetectionError, SchemaSpec, detect_schema, get_schema

__all__ = [
    "ARCHIVE", "KEEP", "PROJECT_SUFFIX", "ROLES", "SCHEMAS", "STATUSES", "UNREVIEWED",
    "Conversation", "Dataset", "DatasetLoadError", "FileFormat", "Issue", "Message", "Project",
    "ProjectError", "SchemaDetectionError", "SchemaSpec", "SourceState",
    "detect_schema", "get_schema", "load", "save", "validate",
]
