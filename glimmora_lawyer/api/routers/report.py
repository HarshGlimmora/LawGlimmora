"""Final report routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from api.deps import require_profile
from api.errors import DomainError
from modules.case.services.case_service import get_case
from modules.evidence_vault.services.report_export_service import (
    export_json, export_pdf, export_text,
)
from modules.evidence_vault.services.report_generation_service import (
    generate_final_report, load_dashboard_cache, load_final_report,
)

router = APIRouter(prefix="/api/cases/{case_id}/report", tags=["report"])


def _ensure_case(case_id: int, uid: int) -> None:
    if not get_case(uid, case_id):
        raise DomainError("case_not_found", "Case not found.", status_code=404)


@router.get("")
def get_report(case_id: int, uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    report = load_final_report(case_id)
    dashboard = load_dashboard_cache(case_id)
    return {
        "report": report.model_dump(mode="json") if report else None,
        "dashboard": dashboard,
    }


@router.post("/generate")
def post_generate_report(case_id: int, uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    report = generate_final_report(user_id=uid, case_id=case_id)
    return report.model_dump(mode="json")


@router.get("/export/{fmt}")
def get_export(case_id: int, fmt: str, uid: int = Depends(require_profile)) -> Response:
    _ensure_case(case_id, uid)
    report = load_final_report(case_id)
    if not report:
        raise DomainError("report_not_generated",
                          "Generate the final report before exporting.",
                          status_code=409)
    if fmt == "json":
        return Response(content=export_json(report), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="report-{case_id}.json"'})
    if fmt == "text":
        return Response(content=export_text(report), media_type="text/plain",
                        headers={"Content-Disposition": f'attachment; filename="report-{case_id}.txt"'})
    if fmt == "pdf":
        return Response(content=export_pdf(report), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="report-{case_id}.pdf"'})
    raise DomainError("bad_format", f"Unknown export format: {fmt!r}.", status_code=400)
