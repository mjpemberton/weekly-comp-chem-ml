import csv
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta


def format_week_date_end(week: str) -> str:
    """
    Convert YYYY-MM-DD to '1 January 2026'.
    """
    dt = datetime.strptime(week, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%B %Y')}"

def format_week_date_start(week: str) -> str:
    """
    Convert YYYY-MM-DD to date minus 6 days, formatted as '1 January 2026'.
    """
    dt = datetime.strptime(week, "%Y-%m-%d") - timedelta(days=6)
    return f"{dt.day} {dt.strftime('%B %Y')}"


def read_csv(csv_path: Path):
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("CSV file is empty")

    required_fields = {"title", "journal", "link", "category"}
    missing = required_fields - set(rows[0].keys())
    if missing:
        raise ValueError(f"Missing required CSV columns: {missing}")

    return rows


def group_by_category(rows):
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["category"]].append({
            "title": row["title"],
            "journal": row["journal"],
            "link": row["link"],
        })

    return grouped


def write_markdown(grouped, output_path: Path, week: str):
    start_date = format_week_date_start(week)
    end_date = format_week_date_end(week)
    title = f"Weekly Digest: {end_date}"

    lines = []

    # Front matter for Jekyll / GitHub Pages
    lines.extend([
        "---",
        f"title: {title}",
        "---",
        "",
    ])

    # Page title
    lines.extend([
        f"# {title}",
        "",
        f"Weekly literature digest covering recent research in computational chemistry and machine learning published between {start_date} and {end_date}.",
        "← [Back to Weekly Digest Index](/contents.md)",
        "",
        "",
    ])

    for category in sorted(grouped.keys()):
        papers = grouped[category]

        if not papers:
            continue

        lines.append(f"## {category}")
        lines.append("")

        for p in papers:
            lines.append(
                f"- **{p['title']}**  \n"
                f"  *{p['journal']}* – [link]({p['link']})"
            )

        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    week = "2026-01-01"

    csv_path = Path(f"weeks/{week}.csv")
    output_path = Path(f"weeks/{week}.md")

    rows = read_csv(csv_path)
    grouped = group_by_category(rows)
    write_markdown(grouped, output_path, week)

    print(f"Markdown file written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
