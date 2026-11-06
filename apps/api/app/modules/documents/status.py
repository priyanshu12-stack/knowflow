"""Status vocabularies (ADR-000 G-1).

`DocumentStatus` is what the user sees (PRD §5.2). `JobStatus` + `JobStage` describe the worker's
progress (TRD §8). Both are updated in the same transaction so they never disagree.
"""

from typing import Literal, get_args

DocumentStatus = Literal["queued", "extracting", "chunking", "embedding", "ready", "failed"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]
JobStage = Literal["extracting", "chunking", "embedding"]

DOCUMENT_STATUSES: tuple[str, ...] = get_args(DocumentStatus)
JOB_STATUSES: tuple[str, ...] = get_args(JobStatus)
JOB_STAGES: tuple[str, ...] = get_args(JobStage)

# A job in one of these states still owns the document; never queue a second one alongside it.
ACTIVE_JOB_STATUSES: tuple[JobStatus, ...] = ("queued", "running")
