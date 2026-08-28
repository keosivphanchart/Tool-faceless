import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.analyzer import ReportInputError, analyze, load_dataframe
from app.config import settings
from app.db import Report, get_db, init_db
from app.delivery import DeliveryNotConfigured, send_email, send_telegram
from app.pdf_report import build_pdf

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    Path(settings.reports_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="IT Report Generator", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def api_analyze(file: UploadFile, db: Session = Depends(get_db)):
    raw = await file.read()
    try:
        df = load_dataframe(raw, file.filename or "upload.csv")
        report = analyze(df)
    except ReportInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    pdf_bytes = build_pdf(report)

    record = Report(filename=file.filename or "upload.csv", summary_json=json.dumps(report), pdf_path="")
    db.add(record)
    db.commit()
    db.refresh(record)

    pdf_path = Path(settings.reports_dir) / f"{record.id}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    record.pdf_path = str(pdf_path)
    db.commit()

    return {"id": record.id, **report}


@app.get("/api/reports")
def api_list_reports(db: Session = Depends(get_db)):
    reports = db.query(Report).order_by(Report.created_at.desc()).limit(50).all()
    return [
        {"id": r.id, "filename": r.filename, "created_at": r.created_at, "summary": r.summary()["summary"]}
        for r in reports
    ]


def _get_report_or_404(report_id: int, db: Session) -> Report:
    record = db.get(Report, report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return record


@app.get("/api/reports/{report_id}")
def api_get_report(report_id: int, db: Session = Depends(get_db)):
    record = _get_report_or_404(report_id, db)
    return {"id": record.id, "filename": record.filename, "created_at": record.created_at, **record.summary()}


@app.get("/api/reports/{report_id}/pdf")
def api_get_report_pdf(report_id: int, db: Session = Depends(get_db)):
    record = _get_report_or_404(report_id, db)
    return FileResponse(record.pdf_path, media_type="application/pdf", filename=f"report-{record.id}.pdf")


@app.post("/api/reports/{report_id}/send-email")
def api_send_email(report_id: int, db: Session = Depends(get_db)):
    record = _get_report_or_404(report_id, db)
    try:
        send_email(Path(record.pdf_path).read_bytes(), record.summary()["summary"], filename=f"report-{record.id}.pdf")
    except DeliveryNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"sent": True}


@app.post("/api/reports/{report_id}/send-telegram")
def api_send_telegram(report_id: int, db: Session = Depends(get_db)):
    record = _get_report_or_404(report_id, db)
    try:
        send_telegram(Path(record.pdf_path).read_bytes(), record.summary()["summary"], filename=f"report-{record.id}.pdf")
    except DeliveryNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"sent": True}


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
