"""TOML configuration reader/writer for index.toml and labels.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import tomli_w

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class SiteConfig:
    """Parsed site configuration from index.toml."""

    title: str = "My Blog"
    description: str = ""
    default_author: str = ""
    timezone: str = "UTC"
    pages: list[PageConfig] = field(default_factory=list)


@dataclass
class PageConfig:
    """A top-level page configuration."""

    id: str
    title: str
    file: str | None = None


@dataclass
class LabelDef:
    """A label definition from labels.toml."""

    id: str
    names: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    is_implicit: bool = False


def parse_site_config(content_dir: Path) -> SiteConfig:
    """Parse index.toml from the content directory."""
    index_path = content_dir / "index.toml"
    if not index_path.exists():
        return SiteConfig()

    data = tomllib.loads(index_path.read_text(encoding="utf-8"))
    site_data = data.get("site", {})

    pages: list[PageConfig] = []
    for page_data in data.get("pages", []):
        if "id" not in page_data:
            msg = f"Page entry missing required 'id' field: {page_data}"
            raise ValueError(msg)
        pages.append(
            PageConfig(
                id=page_data["id"],
                title=page_data.get("title", page_data["id"].title()),
                file=page_data.get("file"),
            )
        )

    return SiteConfig(
        title=site_data.get("title", "My Blog"),
        description=site_data.get("description", ""),
        default_author=site_data.get("default_author", ""),
        timezone=site_data.get("timezone", "UTC"),
        pages=pages,
    )


def parse_labels_config(content_dir: Path) -> dict[str, LabelDef]:
    """Parse labels.toml from the content directory.

    Returns a dict of label_id -> LabelDef.
    """
    labels_path = content_dir / "labels.toml"
    if not labels_path.exists():
        return {}

    data = tomllib.loads(labels_path.read_text(encoding="utf-8"))
    labels_data: dict[str, Any] = data.get("labels", {})

    result: dict[str, LabelDef] = {}
    for label_id, label_info in labels_data.items():
        names = label_info.get("names", [])
        # Handle both parent (single) and parents (list)
        raw_parent = label_info.get("parent")
        raw_parents = label_info.get("parents", [])
        parents: list[str] = []
        if raw_parent:
            parents.append(str(raw_parent).removeprefix("#"))
        for p in raw_parents:
            parents.append(str(p).removeprefix("#"))

        result[label_id] = LabelDef(
            id=label_id,
            names=names,
            parents=parents,
        )

    return result


def write_labels_config(content_dir: Path, labels: dict[str, LabelDef]) -> None:
    """Write labels back to labels.toml."""
    labels_data: dict[str, Any] = {}
    for label_id, label_def in labels.items():
        entry: dict[str, Any] = {"names": label_def.names}
        if len(label_def.parents) == 1:
            entry["parent"] = f"#{label_def.parents[0]}"
        elif len(label_def.parents) > 1:
            entry["parents"] = [f"#{p}" for p in label_def.parents]
        labels_data[label_id] = entry

    labels_path = content_dir / "labels.toml"
    labels_path.write_bytes(tomli_w.dumps({"labels": labels_data}).encode("utf-8"))


def write_site_config(content_dir: Path, config: SiteConfig) -> None:
    """Write site configuration back to index.toml."""
    site_data: dict[str, Any] = {
        "title": config.title,
        "description": config.description,
        "default_author": config.default_author,
        "timezone": config.timezone,
    }

    pages_data: list[dict[str, Any]] = []
    for page in config.pages:
        entry: dict[str, Any] = {"id": page.id, "title": page.title}
        if page.file is not None:
            entry["file"] = page.file
        pages_data.append(entry)

    index_path = content_dir / "index.toml"
    index_path.write_bytes(tomli_w.dumps({"site": site_data, "pages": pages_data}).encode("utf-8"))
