from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS_DIR = ROOT / "docs"
WEEKS_DIR = DOCS_DIR / "weeks"

ARCHIVE_PATH = DOCS_DIR / "archive.md"
MKDOCS_PATH = ROOT / "mkdocs.yml"

NAV_START = "      # BEGIN AUTO-GENERATED WEEKLY NAV"
NAV_END = "      # END AUTO-GENERATED WEEKLY NAV"


def parse_week_date(path: Path) -> date:
    """Extract the week-ending date from a YYYY-MM-DD.md filename"""
    try:
        return datetime.strptime(path.stem, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"Unexpected weekly filename: {path.name}. "
            "Expected YYYY-MM-DD.md"
        ) from exc


def get_weekly_pages() -> list[tuple[date, Path]]:
    """Return weekly Markdown files in reverse chronological order."""
    pages = [
        (parse_week_date(path), path)
        for path in WEEKS_DIR.glob("*.md")
    ]

    return sorted(pages, key=lambda item: item[0], reverse=True)

def human_date(value: date) -> str:
    """Format a date as '6 August 2026'."""
    return f"{value.day} {value.strftime('%B %Y')}"

def literature_date_range(end_date: date) -> str:
    """Format the seven-day literature window ending on end_date."""
    start_date = end_date - timedelta(days=6)

    if start_date.year == end_date.year:
        if start_date == end_date.month:
            return (
                f"{start_date.day} - {end_date.day} "
                f"{end_date.strftime('%B %Y')}"
            )

        return (
            f"{start_date.day} {start_date.strftime('%B')} - "
            f"{end_date.day} {end_date.strftime('%B %Y')}"
        )

    return f"{human_date(start_date)} - {human_date(end_date)}"

def build_archive(pages: list[tuple[date, Path]]) -> str:
    """Generate the archive Markdown page."""
    lines = [
        "---",
        'title: "Weekly Digest Archive"',
        "---",
        "",
        "# Weekly Digest Archive",
        "",
        (
            "This page provides an archive of weekly literature digests "
            "covering recent research at the intersection of machine "
            "learning and chemistry."
        ),
        "",
        (
            "Each entry summarizes publications released during the "
            "**seven-day period leading up to the listed date**. "
            "Digests are ordered reverse-chronologically, with the most "
            "recent updates shown first."
        ),
        "",
    ]

    current_year = None

    for end_date, path in pages:
        if end_date.year != current_year:
            current_year = end_date.year

            if len(lines) > 12:
                lines.append("---")
                lines.append("")

            lines.append(f"## {current_year}")
            lines.append("")

        relative_path = path.relative_to(DOCS_DIR).as_posix()

        lines.append(
            f"- **[Week ending {human_date(end_date)}]"
            f"({relative_path})**  "
        )
        lines.append(
            f"  *(Literature published "
            f"{literature_date_range(end_date)})*"
        )
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            (
                "Updates are added weekly. Older entries remain "
                "permanently archived for reference."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def build_navigation(pages: list[tuple[date, Path]]) -> list[str]:
    """Generate year/month/week navigation entries."""
    grouped: dict[int, dict[int, list[tuple[date, Path]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for end_date, path in pages:
        grouped[end_date.year][end_date.month].append((end_date, path))

    lines: list[str] = []

    for year in sorted(grouped, reverse=True):
        lines.append(f'      - "{year}":')

        for month in sorted(grouped[year], reverse=True):
            month_name = date(year, month, 1).strftime("%B")
            lines.append(f'          - "{month_name}":')

            month_pages = sorted(
                grouped[year][month],
                key=lambda item: item[0],
                reverse=True,
            )

            for end_date, path in month_pages:
                relative_path = path.relative_to(DOCS_DIR).as_posix()

                lines.append(
                    f'              - "{human_date(end_date)}": '
                    f"{relative_path}"
                )

    return lines


def update_navigation(generated_lines: list[str]) -> None:
    """Replace only the auto-generated region of mkdocs.yml."""
    lines = MKDOCS_PATH.read_text(encoding="utf-8").splitlines()

    try:
        start = lines.index(NAV_START)
        end = lines.index(NAV_END)
    except ValueError as exc:
        raise RuntimeError(
            "Could not find the auto-generated navigation markers "
            "in mkdocs.yml"
        ) from exc

    updated = (
        lines[: start + 1]
        + generated_lines
        + lines[end:]
    )

    MKDOCS_PATH.write_text(
        "\n".join(updated) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    pages = get_weekly_pages()

    if not pages:
        raise RuntimeError(
            f"No weekly Markdown files found in {WEEKS_DIR}"
        )

    ARCHIVE_PATH.write_text(
        build_archive(pages),
        encoding="utf-8",
    )

    update_navigation(build_navigation(pages))

    print(f"Updated site metadata for {len(pages)} weekly digests.")
    print(f"Newest digest: {human_date(pages[0][0])}")
    print(f"Oldest digest: {human_date(pages[-1][0])}")


if __name__ == "__main__":
    main()