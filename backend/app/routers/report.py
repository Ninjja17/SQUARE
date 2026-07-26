"""Report router — POST /api/report/generate, GET /api/report/{id}/pdf."""
from __future__ import annotations

import io
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.models.schemas import ExecutiveReport, RiskReport, ROIReport, SimulationResult
from app.routers.agents import _agent_cache
from app.routers.risk import _risk_cache
from app.routers.roi import _roi_cache
from app.routers.simulate import _sim_cache
from app.services.deployment_advisor import generate_deployment_plan

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/report", tags=["report"])

_report_cache: dict[str, dict] = {}


class ReportRequest(BaseModel):
    workflow_id: str


@router.post("/generate", response_model=ExecutiveReport)
async def generate_report(req: ReportRequest):
    risk_raw = _risk_cache.get(req.workflow_id)
    roi_raw = _roi_cache.get(req.workflow_id)
    sim_raw = _sim_cache.get(req.workflow_id)
    agents_raw = _agent_cache.get(req.workflow_id)

    if not risk_raw:
        raise HTTPException(status_code=404, detail="Risk report not found — run /api/risk/analyze first")
    if not roi_raw:
        raise HTTPException(status_code=404, detail="ROI report not found — run /api/roi/analyze first")
    if not sim_raw:
        raise HTTPException(status_code=404, detail="Simulation results not found")

    risk = RiskReport(**risk_raw)
    roi = ROIReport(**roi_raw)
    sim_results = [SimulationResult(**s) for s in sim_raw]

    plan = await generate_deployment_plan(
        workflow_id=req.workflow_id,
        risk_report=risk,
        roi_report=roi,
        simulation_results=sim_results,
    )

    # Automation score: weighted combination of success rates and risk
    success_rates = [r.success_rate for r in sim_results]
    avg_success = sum(success_rates) / len(success_rates) if success_rates else 0.0
    automation_score = round((avg_success * 0.7 + (1 - risk.overall_score / 100) * 0.3) * 100, 1)

    report = ExecutiveReport(
        workflow_id=req.workflow_id,
        automation_score=automation_score,
        risk_report=risk,
        roi_report=roi,
        deployment_plan=plan,
        go_no_go=plan.go_no_go,
    )
    _report_cache[req.workflow_id] = report.model_dump(mode="json")
    return report


@router.get("/{workflow_id}/pdf")
async def download_pdf(workflow_id: str):
    report_data = _report_cache.get(workflow_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not generated yet")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm,
                                topMargin=2 * cm, bottomMargin=2 * cm)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("⚡ Square — Executive Readiness Report", styles["Title"]))
        story.append(Spacer(1, 0.4 * cm))

        r = report_data
        story.append(Paragraph(f"Automation Score: {r['automation_score']}%", styles["Heading2"]))
        story.append(Paragraph(f"Go / No-Go: {r['go_no_go']}", styles["Heading2"]))
        story.append(Paragraph(f"Overall Risk Score: {r['risk_report']['overall_score']}", styles["Normal"]))
        story.append(Paragraph(f"Year 1 ROI: {r['roi_report']['roi_percent_year1']}%", styles["Normal"]))
        story.append(Paragraph(f"Annual Savings: ${r['roi_report']['annual_savings']:,.0f}", styles["Normal"]))
        story.append(Paragraph(f"Payback Period: {r['roi_report']['payback_period_months']} months", styles["Normal"]))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("Risk Breakdown", styles["Heading2"]))
        for cat in r["risk_report"]["categories"]:
            story.append(Paragraph(f"• {cat['name']}: {cat['score']}/100 — {cat['justification']}", styles["Normal"]))

        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Deployment Phases", styles["Heading2"]))
        for phase in r["deployment_plan"]["phases"]:
            story.append(Paragraph(
                f"• {phase['name']}: {phase['scope_percent']}% scope, "
                f"{phase['human_oversight_percent']}% human oversight — {phase['success_criteria']}",
                styles["Normal"],
            ))

        doc.build(story)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=square_report_{workflow_id[:8]}.pdf"},
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF export requires reportlab — install it on the server")
