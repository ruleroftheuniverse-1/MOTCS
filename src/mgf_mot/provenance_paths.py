"""Host-independent canonical paths for repository dependency provenance.

This module deliberately parses path strings without asking the host operating
system to interpret them.  It therefore handles Windows and POSIX checkout
forms identically on every supported host and never resolves symlinks.
"""

from __future__ import annotations

from pathlib import Path
import re


class RepositoryProvenancePathError(ValueError):
    """Raised when a dependency path cannot be represented unambiguously."""


_DRIVE = re.compile(r"^(?P<drive>[A-Za-z]):(?P<tail>.*)$")


def _text(value: str | Path, *, name: str) -> str:
    result = str(value)
    if not result:
        raise RepositoryProvenancePathError(f"{name} must not be empty")
    if "\x00" in result:
        raise RepositoryProvenancePathError(f"{name} contains a NUL byte")
    return result


def _split(value: str, *, name: str) -> tuple[str, str | None, tuple[str, ...]]:
    """Return (style, drive, segments) without host-dependent Path parsing."""

    if value.startswith(("\\\\", "//")):
        raise RepositoryProvenancePathError(f"{name} must not be a UNC path")
    normalized = value.replace("\\", "/")
    if normalized.endswith("/"):
        raise RepositoryProvenancePathError(f"{name} must not have a trailing separator")
    if "//" in normalized:
        raise RepositoryProvenancePathError(f"{name} contains an ambiguous repeated separator")

    drive_match = _DRIVE.match(normalized)
    if drive_match:
        tail = drive_match.group("tail")
        if not tail.startswith("/"):
            raise RepositoryProvenancePathError(
                f"{name} is drive-qualified but not an absolute Windows path"
            )
        style = "windows_absolute"
        drive = drive_match.group("drive")
        body = tail[1:]
    elif normalized.startswith("/"):
        style = "posix_absolute"
        drive = None
        body = normalized[1:]
    else:
        style = "relative"
        drive = None
        body = normalized

    segments = tuple(body.split("/"))
    if not segments or any(segment == "" for segment in segments):
        raise RepositoryProvenancePathError(f"{name} does not identify a dependency file")
    if any(segment in {".", ".."} for segment in segments):
        raise RepositoryProvenancePathError(
            f"{name} contains an ambiguous '.' or '..' segment"
        )
    return style, drive, segments


def canonical_repository_path(
    path: str | Path,
    *,
    repository_root: str | Path | None = None,
) -> str:
    """Return one repository-relative POSIX dependency identity.

    Relative input is interpreted as already relative to the repository root.
    Absolute input is accepted only when an explicit matching repository root
    is supplied.  Case and Unicode code points are preserved.  No filesystem
    access, normalization through ``resolve()``, or symlink expansion occurs.
    """

    value = _text(path, name="path")
    style, drive, segments = _split(value, name="path")

    if style == "relative":
        canonical = "/".join(segments)
    else:
        if repository_root is None:
            raise RepositoryProvenancePathError(
                "absolute dependency paths require an explicit repository_root"
            )
        root_value = _text(repository_root, name="repository_root")
        root_style, root_drive, root_segments = _split(
            root_value, name="repository_root"
        )
        if root_style != style:
            raise RepositoryProvenancePathError(
                "path and repository_root use incompatible absolute path styles"
            )
        if style == "windows_absolute" and drive.casefold() != root_drive.casefold():
            raise RepositoryProvenancePathError(
                "path and repository_root use different Windows drives"
            )
        if len(segments) <= len(root_segments) or segments[: len(root_segments)] != root_segments:
            raise RepositoryProvenancePathError(
                "dependency path is outside the explicitly supplied repository_root"
            )
        canonical = "/".join(segments[len(root_segments) :])

    if not canonical or canonical.startswith("/") or "\\" in canonical:
        raise RepositoryProvenancePathError("canonical dependency path is invalid")
    if _DRIVE.match(canonical):
        raise RepositoryProvenancePathError("canonical dependency path has a drive prefix")
    return canonical


def is_canonical_repository_path(value: str) -> bool:
    """Return whether *value* is already in canonical serialized form."""

    try:
        return canonical_repository_path(value) == value
    except RepositoryProvenancePathError:
        return False
