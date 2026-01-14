from app.schemas.query import ChartData


def format_chart_data(rows: list[dict]) -> ChartData:
    """Convert database rows to Chart.js format."""
    if not rows:
        return ChartData(labels=[], datasets=[])

    columns = list(rows[0].keys())
    labels = [str(row[columns[0]]) for row in rows]

    datasets = []
    for col in columns[1:]:
        datasets.append({
            "label": col.replace("_", " ").title(),
            "data": [float(row[col]) if row[col] else 0 for row in rows]
        })

    return ChartData(labels=labels, datasets=datasets)
