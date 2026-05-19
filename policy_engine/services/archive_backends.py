"""Pluggable archive backends for audit log cold storage.

Supports two backends:
  - LocalArchiveBackend: gzip-compressed JSON files on the local filesystem
  - S3ArchiveBackend:    gzip-compressed JSON uploaded to AWS S3 via boto3

Security model
--------------
HIPAA Safe Harbor requires that cold-storage archives do not contain PHI.
_serialize_log() uses an *allowlist* approach: only fields that are
structurally guaranteed to be PHI-free are retained.  Any column not
explicitly listed in AUDIT_LOG_SAFE_FIELDS is dropped before writing.

Usage:
    from policy_engine.services.archive_backends import get_archive_backend
    from policy_engine.config import settings

    backend = get_archive_backend(settings)
    result  = backend.write(logs)
"""

import gzip
import json
import os
import pathlib
from datetime import datetime
from typing import Any, Dict, FrozenSet, List, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Allowlist — only these fields are safe to write to cold storage.
# Everything else (arguments, data_touched, reason, log_metadata / metadata,
# user_id, agent_name) is dropped because it may contain PHI.
# ---------------------------------------------------------------------------
AUDIT_LOG_SAFE_FIELDS: FrozenSet[str] = frozenset([
    "id",
    "timestamp",
    "agent_id",
    "tool_name",
    "system_accessed",
    "decision",
    "policy_ids",
])

# Legacy name kept for backwards-compatible test imports; tests should prefer
# checking against AUDIT_LOG_SAFE_FIELDS.
AUDIT_LOG_PHI_FIELDS: List[str] = ["arguments", "data_touched"]


# ---------------------------------------------------------------------------
# Serialisation helper
# ---------------------------------------------------------------------------

def _serialize_log(log: Any) -> Dict[str, Any]:
    """Convert an AuditLog ORM object (or dict) to a safe archive record.

    Uses an allowlist: only fields in AUDIT_LOG_SAFE_FIELDS are kept.
    datetime values are converted to ISO-8601 strings.
    """
    if isinstance(log, dict):
        raw = dict(log)
    else:
        # SQLAlchemy ORM object — pull already-loaded column values.
        raw = {
            k: v
            for k, v in log.__dict__.items()
            if not k.startswith("_")
        }

    # Retain only safe, non-PHI fields.
    record: Dict[str, Any] = {
        k: v for k, v in raw.items() if k in AUDIT_LOG_SAFE_FIELDS
    }

    # Serialise datetime → ISO string so json.dumps works.
    for key, value in list(record.items()):
        if isinstance(value, datetime):
            record[key] = value.isoformat()

    return record


# ---------------------------------------------------------------------------
# Protocol (structural subtyping — no inheritance required)
# ---------------------------------------------------------------------------

@runtime_checkable
class ArchiveBackend(Protocol):
    """Any object that implements write() satisfies this protocol."""

    def write(self, logs: List[Any]) -> Dict[str, Any]:  # pragma: no cover
        """Persist logs and return archival metadata."""
        ...


# ---------------------------------------------------------------------------
# Local filesystem backend
# ---------------------------------------------------------------------------

class LocalArchiveBackend:
    """Writes gzip-compressed JSON to a local directory.

    Args:
        archive_dir: Absolute path where .json.gz files are created.
                     Must be an existing directory or creatable path.
                     Path traversal sequences are rejected.

    Raises:
        ValueError: If archive_dir is empty or contains traversal sequences.
    """

    def __init__(self, archive_dir: str) -> None:
        if not archive_dir:
            raise ValueError(
                "ARCHIVE_LOCAL_PATH must be set when ARCHIVE_BACKEND=local"
            )
        # Resolve to an absolute path and reject traversal sequences.
        resolved = pathlib.Path(archive_dir).resolve()
        if ".." in pathlib.Path(archive_dir).parts:
            raise ValueError(
                f"ARCHIVE_LOCAL_PATH '{archive_dir}' contains path traversal sequences."
            )
        self._archive_dir = str(resolved)

    def write(self, logs: List[Any]) -> Dict[str, Any]:
        """Serialise logs (PHI stripped via allowlist) to a timestamped .json.gz.

        Returns:
            Dict with keys: archive_id, archived_count, storage_location.
        """
        os.makedirs(self._archive_dir, exist_ok=True)

        archive_id = f"archive_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        filename = f"{archive_id}.json.gz"
        # Use pathlib to safely join so no separator injection is possible.
        filepath = str(pathlib.Path(self._archive_dir) / filename)

        records = [_serialize_log(log) for log in logs]

        # CRIT-008 — fsync + stat round-trip BEFORE returning success so
        # the retention sweep cannot delete DB rows whose archive write
        # is still buffered in page cache.
        with gzip.open(filepath, "wt", encoding="utf-8") as fh:
            json.dump(records, fh, default=str)
            fh.flush()
            try:
                # `gzip.GzipFile` does not always expose fileno() on every
                # platform — best-effort fsync, then re-stat the path.
                os.fsync(fh.fileno())
            except (AttributeError, OSError):
                pass

        # Stat verifies the bytes hit the filesystem. Raise on any error
        # so archive_and_delete refuses to proceed.
        stat = os.stat(filepath)
        if stat.st_size <= 0:
            raise IOError(
                f"LocalArchiveBackend: archive {filepath} is zero bytes — "
                "refusing to acknowledge a successful write."
            )

        return {
            "archive_id": archive_id,
            "archived_count": len(records),
            "storage_location": filepath,
            "archived_at": datetime.utcnow().isoformat(),
            "size_bytes": stat.st_size,
        }


# ---------------------------------------------------------------------------
# S3 backend
# ---------------------------------------------------------------------------

class S3ArchiveBackend:
    """Uploads gzip-compressed JSON to AWS S3 with SSE-KMS encryption.

    Args:
        bucket: S3 bucket name.
        prefix: Key prefix (e.g. "audit-logs/").
        kms_key_id: KMS key ARN or alias for server-side encryption.
                    Defaults to the bucket's default KMS key when empty.

    Raises:
        ValueError: If bucket is empty.
        ImportError: If boto3 is not installed.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "audit-logs/",
        kms_key_id: str = "",
    ) -> None:
        if not bucket:
            raise ValueError(
                "ARCHIVE_S3_BUCKET must be set when ARCHIVE_BACKEND=s3"
            )
        try:
            import boto3  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "boto3 is required for S3ArchiveBackend. "
                "Install it with: pip install boto3"
            ) from exc

        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/"
        self._kms_key_id = kms_key_id
        self._s3 = boto3.client("s3")

    def write(self, logs: List[Any]) -> Dict[str, Any]:
        """Serialise logs (PHI stripped via allowlist) and upload to S3.

        Encryption: SSE-KMS is applied on every put_object call.
        If kms_key_id is empty the bucket's default KMS key is used.

        Returns:
            Dict with keys: archive_id, archived_count, storage_location.
        """
        archive_id = f"archive_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        key = f"{self._prefix}{archive_id}.json.gz"

        records = [_serialize_log(log) for log in logs]
        payload = gzip.compress(
            json.dumps(records, default=str).encode("utf-8")
        )

        put_kwargs: Dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": payload,
            "ContentEncoding": "gzip",
            "ContentType": "application/json",
            "ServerSideEncryption": "aws:kms",
        }
        if self._kms_key_id:
            put_kwargs["SSEKMSKeyId"] = self._kms_key_id

        put_response = self._s3.put_object(**put_kwargs)

        # CRIT-008 — verify the object actually landed BEFORE returning
        # success so the retention sweep cannot delete DB rows whose
        # archive object is missing.
        etag = put_response.get("ETag")
        if not etag:
            raise IOError(
                f"S3ArchiveBackend: put_object for {key} returned no ETag — "
                "refusing to acknowledge a successful write."
            )
        # head_object round-trip confirms the object is durably visible.
        try:
            head = self._s3.head_object(Bucket=self._bucket, Key=key)
        except Exception as exc:  # pragma: no cover — network/IAM failures
            raise IOError(
                f"S3ArchiveBackend: head_object failed for {key} after put "
                f"(ETag={etag}). Refusing to claim success: {exc}"
            ) from exc
        if head.get("ETag") != etag:
            raise IOError(
                f"S3ArchiveBackend: head_object ETag mismatch for {key} "
                f"(put={etag!r}, head={head.get('ETag')!r})."
            )

        return {
            "archive_id": archive_id,
            "archived_count": len(records),
            "storage_location": f"s3://{self._bucket}/{key}",
            "archived_at": datetime.utcnow().isoformat(),
            "etag": etag,
            "size_bytes": head.get("ContentLength"),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_archive_backend(cfg: Any) -> ArchiveBackend:
    """Return the configured ArchiveBackend instance.

    Args:
        cfg: Any object with ARCHIVE_BACKEND, ARCHIVE_LOCAL_PATH,
             ARCHIVE_S3_BUCKET, ARCHIVE_S3_PREFIX, ARCHIVE_S3_KMS_KEY_ID
             attributes (matches policy_engine.config.Settings).

    Raises:
        ValueError: Unknown backend value or missing required path/bucket.
    """
    backend = getattr(cfg, "ARCHIVE_BACKEND", "local").lower()

    if backend == "local":
        return LocalArchiveBackend(
            archive_dir=getattr(cfg, "ARCHIVE_LOCAL_PATH", "")
        )
    if backend == "s3":
        return S3ArchiveBackend(
            bucket=getattr(cfg, "ARCHIVE_S3_BUCKET", ""),
            prefix=getattr(cfg, "ARCHIVE_S3_PREFIX", "audit-logs/"),
            kms_key_id=getattr(cfg, "ARCHIVE_S3_KMS_KEY_ID", ""),
        )

    raise ValueError(
        f"Unknown ARCHIVE_BACKEND={backend!r}. Valid values: 'local', 's3'."
    )
