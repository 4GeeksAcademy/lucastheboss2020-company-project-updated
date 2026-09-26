from fastapi import FastAPI, HTTPException, status
from .models import AnalysisResult, TRFRecord, AnalysisMetrics, InvalidRecordDetail
from .data import store_analysis, get_analysis, get_all_analyses

app = FastAPI(title="TrackFlow Incidents API")


@app.get("/incidents/analyses")
def list_analyses():
    """List all stored analysis results."""
    return get_all_analyses()


@app.get("/incidents/analyses/{analysis_id}")
def get_analysis_result(analysis_id: str):
    """Get a specific analysis result by ID."""
    result = get_analysis(analysis_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    return result


@app.post("/incidents/analyses", status_code=status.HTTP_201_CREATED)
def create_analysis_result(payload: dict):
    """Store an analysis result (typically called after CSV processing)."""
    return store_analysis(payload)


@app.get("/incidents/analyses/{analysis_id}/export")
def export_analysis_csv(analysis_id: str):
    """Export analysis result as CSV download."""
    result = get_analysis(analysis_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )

    metrics = result.get("metrics", {})
    lines = ["Metric,Value"]

    lines.append(f"Format,TRF")
    lines.append(f"Total Records Processed,{metrics.get('total_processed', '')}")
    lines.append(f"Valid Records,{metrics.get('valid_records', '')}")
    lines.append(f"Invalid Records,{metrics.get('invalid_records', '')}")

    for carrier, count in metrics.get("carrier_breakdown", {}).items():
        lines.append(f'Carrier - {carrier},{count}')

    for cat, count in metrics.get("category_breakdown", {}).items():
        lines.append(f'Category - {cat},{count}')

    for status, count in metrics.get("status_breakdown", {}).items():
        lines.append(f'Status - {status.title()},{count}')

    avg_dv = metrics.get("average_declared_value")
    lines.append(f'Average Declared Value (€),{avg_dv:.2f}' if avg_dv else 'Average Declared Value (€),N/A')

    invalids = result.get("invalid_records", [])
    lines.append(f"Invalid Record Count,{len(invalids)}")

    if invalids:
        lines.append("")
        lines.append("Row Number,Tracking ID,Errors")
        for rec in invalids:
            errs = " | ".join(rec.get("errors", []))
            # Proper CSV escaping
            errs_escaped = f'"{errs}"' if "," in errs else errs
            lines.append(f'{rec.get("row_number", "")},{rec.get("tracking_id", "")},{errs_escaped}')

    csv_content = "\n".join(lines)

    from fastapi.responses import PlainTextResponse
    from fastapi import Response
    import re

    sanitized_id = re.sub(r'[^a-zA-Z0-9-]', '', analysis_id)[:8]
    filename = f"incident-analysis-trf-{sanitized_id}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )