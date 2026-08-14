from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]

DATA_WEEKS_DIR = ROOT / "data" / "weeks"
DOCS_WEEKS_DIR = ROOT / "docs" / "weeks"
UPDATE_SITE_SCRIPT = ROOT / "scripts" / "update_site.py"

REQUIRED_FIELDS = (
    "title",
    "journal",
    "link",
    "category",
)

CATEGORIES = (
    "Autonomous Labs, Agents & AI-Driven Experimentation",
    "Data, Benchmarks, Tools & Reproducibility",
    "Drug Discovery, ADME & Chemical Biology",
    "Generative Models & Molecular Design",
    "Machine-Learned Potentials & Molecular Simulation",
    "Molecular Representation, Graphs & Foundation Models",
    "Quantum Chemistry & Electronic Structure with ML",
    "Reaction Prediction, Mechanisms & Synthesis Planning",
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate and validate a weekly literature digest "
            "from a CSV file."
        )
    )

    parser.add_argument(
        "csv_path",
        type=Path,
        help=(
            "Path to the weekly CSV file. If --week is omitted, "
            "the filename must be YYYY-MM-DD.csv."
        ),
    )

    parser.add_argument(
        "--week",
        help=(
            "Week-ending date in YYYY-MM-DD format. "
            "Defaults to the CSV filename."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow an existing week's CSV and Markdown files to be replaced.",
    )

    return parser.parse_args()


def parse_week(value: str) -> date:
    """Parse a YYYY-MM-DD week-ending date."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"Invalid week '{value}'. Expected YYYY-MM-DD."
        ) from exc


def determine_week(csv_path: Path, week_argument: str | None) -> date:
    """Determine the week-ending date from --week or the CSV filename."""
    if week_argument is not None:
        return parse_week(week_argument)

    if csv_path.suffix.lower() != ".csv":
        raise ValueError(
            "Input file must have a .csv extension."
        )

    return parse_week(csv_path.stem)


def validate_url(value: str, row_number: int) -> None:
    """Check that a URL looks like an HTTP(S) URL."""
    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            f"Row {row_number}: invalid URL '{value}'."
        )


def read_and_validate_csv(csv_path: Path) -> list[dict[str, str]]:
    """Read, normalize, and validate the publication CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV file not found: {csv_path}"
        )

    if not csv_path.is_file():
        raise ValueError(
            f"CSV path is not a file: {csv_path}"
        )

    with csv_path.open(
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row.")

        fields = tuple(
            field.strip()
            for field in reader.fieldnames
        )

        if set(fields) != set(REQUIRED_FIELDS):
            missing = set(REQUIRED_FIELDS) - set(fields)
            unexpected = set(fields) - set(REQUIRED_FIELDS)

            messages = []

            if missing:
                messages.append(
                    "missing columns: "
                    + ", ".join(sorted(missing))
                )

            if unexpected:
                messages.append(
                    "unexpected columns: "
                    + ", ".join(sorted(unexpected))
                )

            raise ValueError(
                "Invalid CSV header (" + "; ".join(messages) + ")."
            )

        rows: list[dict[str, str]] = []

        seen_titles: set[str] = set()
        seen_links: set[str] = set()

        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"Row {row_number}: too many CSV fields."
                )

            normalized = {}

            for field in REQUIRED_FIELDS:
                value = row.get(field)

                if value is None:
                    raise ValueError(
                        f"Row {row_number}: missing '{field}'."
                    )

                value = value.strip()

                if not value:
                    raise ValueError(
                        f"Row {row_number}: '{field}' is empty."
                    )

                normalized[field] = value

            category = normalized["category"]

            if category not in CATEGORIES:
                raise ValueError(
                    f"Row {row_number}: unknown category "
                    f"'{category}'."
                )

            validate_url(
                normalized["link"],
                row_number,
            )

            title_key = normalized["title"].casefold()
            link_key = normalized["link"]

            if title_key in seen_titles:
                raise ValueError(
                    f"Row {row_number}: duplicate title "
                    f"'{normalized['title']}'."
                )

            if link_key in seen_links:
                raise ValueError(
                    f"Row {row_number}: duplicate URL "
                    f"'{normalized['link']}'."
                )

            seen_titles.add(title_key)
            seen_links.add(link_key)

            rows.append(normalized)

    if not rows:
        raise ValueError(
            "CSV contains no publications."
        )

    return rows


def human_date(value: date) -> str:
    """Format a date as '6 August 2026'."""
    return f"{value.day} {value.strftime('%B %Y')}"


def write_canonical_csv(
    rows: list[dict[str, str]],
    output_path: Path,
) -> None:
    """Write a normalized copy of the source CSV."""
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=REQUIRED_FIELDS,
            quoting=csv.QUOTE_ALL,
        )

        writer.writeheader()
        writer.writerows(rows)


def build_markdown(
    rows: list[dict[str, str]],
    week_end: date,
) -> str:
    """Generate the weekly digest Markdown."""
    week_start = week_end - timedelta(days=6)

    end_date = human_date(week_end)
    start_date = human_date(week_start)

    title = f"Weekly Digest: {end_date}"

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        grouped[row["category"]].append(row)

    lines = [
        "---",
        f'title: "{title}"',
        "---",
        "",
        f"# {title}",
        "",
        (
            "Weekly literature digest covering recent research in "
            "computational chemistry and machine learning published "
            f"between {start_date} and {end_date}."
        ),
        "",
        "← [Back to Weekly Digest Archive](../archive.md)",
        "",
    ]

    for category in CATEGORIES:
        papers = grouped.get(category, [])

        if not papers:
            continue

        lines.extend([
            f"## {category}",
            "",
        ])

        for paper in papers:
            lines.extend([
                f"- **{paper['title']}**  ",
                (
                    f"  *{paper['journal']}* – "
                    f"[link]({paper['link']})"
                ),
            ])

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_markdown(
    rows: list[dict[str, str]],
    output_path: Path,
    week_end: date,
) -> None:
    """Write the generated weekly Markdown page."""
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        build_markdown(rows, week_end),
        encoding="utf-8",
    )


def check_overwrite(
    paths: list[Path],
    overwrite: bool,
) -> None:
    """Refuse to replace an existing digest unless explicitly allowed."""
    existing = [
        path
        for path in paths
        if path.exists()
    ]

    if existing and not overwrite:
        formatted = "\n".join(
            f"  - {path.relative_to(ROOT)}"
            for path in existing
        )

        raise FileExistsError(
            "Refusing to overwrite existing files:\n"
            f"{formatted}\n"
            "Use --overwrite if this is intentional."
        )


def update_site() -> None:
    """Regenerate the archive and MkDocs navigation."""
    print("\nUpdating archive and navigation...")

    subprocess.run(
        [
            sys.executable,
            str(UPDATE_SITE_SCRIPT),
        ],
        cwd=ROOT,
        check=True,
    )


def validate_site() -> None:
    """Run a strict MkDocs build."""
    print("\nValidating MkDocs site...")

    subprocess.run(
        [
            "mkdocs",
            "build",
            "--strict",
        ],
        cwd=ROOT,
        check=True,
    )


def show_git_status() -> None:
    """Display the files changed by publication."""
    print("\nGit changes:")

    subprocess.run(
        [
            "git",
            "status",
            "--short",
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> None:
    args = parse_args()

    csv_path = args.csv_path.expanduser().resolve()

    week_end = determine_week(
        csv_path,
        args.week,
    )

    week_string = week_end.isoformat()

    canonical_csv = (
        DATA_WEEKS_DIR / f"{week_string}.csv"
    )

    markdown_path = (
        DOCS_WEEKS_DIR / f"{week_string}.md"
    )

    print(f"Input CSV: {csv_path}")
    print(f"Week ending: {human_date(week_end)}")

    rows = read_and_validate_csv(csv_path)

    print(
        f"Validated {len(rows)} publications "
        "across the expected category schema."
    )

    check_overwrite(
        [
            canonical_csv,
            markdown_path,
        ],
        overwrite=args.overwrite,
    )

    write_canonical_csv(
        rows,
        canonical_csv,
    )

    print(
        f"Wrote structured data: "
        f"{canonical_csv.relative_to(ROOT)}"
    )

    write_markdown(
        rows,
        markdown_path,
        week_end,
    )

    print(
        f"Wrote weekly page: "
        f"{markdown_path.relative_to(ROOT)}"
    )

    update_site()
    validate_site()

    print(
        "\nPublication pipeline completed successfully."
    )

    show_git_status()

    print(
        "\nReview the rendered site with 'mkdocs serve' "
        "before committing."
    )


if __name__ == "__main__":
    main()