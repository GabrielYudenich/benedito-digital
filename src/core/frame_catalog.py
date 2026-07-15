"""Filtering and paging helpers for large frame catalogs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrameCatalogPage:
    number: int
    total_pages: int
    indices: tuple[int, ...]
    total_matches: int


def filter_frame_indices(
    frame_names: list[str],
    statuses: dict[int, dict],
    *,
    query: str = "",
    status_filter: str | None = None,
    excluded_indices: set[int] | None = None,
) -> list[int]:
    normalized_query = query.strip().lower()
    excluded = excluded_indices or set()
    exact_frame = None
    if normalized_query.isdigit():
        exact_frame = int(normalized_query) - 1
    result = []
    for index, filename in enumerate(frame_names):
        status = statuses.get(index, {}).get("status", "unmarked")
        if status_filter == "excluded" and index not in excluded:
            continue
        if status_filter and status_filter != "excluded" and status != status_filter:
            continue
        if exact_frame is not None:
            if index != exact_frame:
                continue
        elif normalized_query and normalized_query not in filename.lower():
            continue
        result.append(index)
    return result


def catalog_page(indices: list[int], page: int, page_size: int) -> FrameCatalogPage:
    safe_size = max(1, int(page_size))
    total_pages = max(1, (len(indices) + safe_size - 1) // safe_size)
    safe_page = max(0, min(int(page), total_pages - 1))
    start = safe_page * safe_size
    return FrameCatalogPage(
        number=safe_page,
        total_pages=total_pages,
        indices=tuple(indices[start : start + safe_size]),
        total_matches=len(indices),
    )
