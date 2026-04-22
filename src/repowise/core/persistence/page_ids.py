"""Helpers for repo-scoped wiki page identifiers."""

from __future__ import annotations

from dataclasses import dataclass

STORAGE_PAGE_DELIMITER = "|"


@dataclass(frozen=True)
class ParsedStoragePageId:
    repository_id: str
    logical_page_id: str


def make_storage_page_id(repository_id: str, logical_page_id: str) -> str:
    return f"{repository_id}{STORAGE_PAGE_DELIMITER}{logical_page_id}"


def parse_storage_page_id(page_id: str) -> ParsedStoragePageId | None:
    if STORAGE_PAGE_DELIMITER not in page_id:
        return None
    repository_id, logical_page_id = page_id.split(STORAGE_PAGE_DELIMITER, 1)
    if not repository_id or not logical_page_id:
        return None
    return ParsedStoragePageId(repository_id=repository_id, logical_page_id=logical_page_id)


def get_logical_page_id(page_id: str) -> str:
    parsed = parse_storage_page_id(page_id)
    return parsed.logical_page_id if parsed is not None else page_id
