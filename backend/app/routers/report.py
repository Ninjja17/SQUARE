"""Report router — POST /api/report/prepare (one-call), POST /api/report/generate, GET /api/report/{id}/pdf."""
from __future__ import annotations

import io
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.models.schemas import ExecutiveReport, GovernanceReport, RiskReport, ROIReport, SimulationResult
from app.routers.agents import _agent_cache
from app.routers.risk import _risk_cache
from app.routers.roi import _roi_cache
from app.routers.simulate import _sim_cache
from app.services.deployment_advisor import generate_deployment_plan

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/report", tags=["report"])

_report_cache: dict[str, dict] = {}


# ─── Shared request model ─────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    workflow_id: str

    @field_validator("workflow_id")
    @classmethod
    def workflow_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("workflow_id must not be empty")
        return v.strip()


# ─── Response model for /prepare ─────────────────────────────────────────────

class PrepareReportResponse(BaseModel):
    workflow_id: str
    governance_summary: str
    risk_report: RiskReport
    roi_report: ROIReport
    executive_report: ExecutiveReport
    go_no_go: str


# ─── One-call orchestration endpoint ─────────────────────────────────────────

@router.post(
    "/prepare",
    response_model=PrepareReportResponse,
    summary="Orchestrated report preparation (one call)",
    description=(
        "Single client-facing endpoint that runs the full post-simulation pipeline in order: "
        "governance check (silent) → risk analysis → ROI analysis → executive report generation. "
        "Prerequisites: workflow analyzed, agents generated, simulation run."
    ),
)
async def prepare_report(req: ReportRequest):
    from app.routers.workflow import _cache as _workflow_cache
    from app.routers.governance import _gov_cache
    from app.services.core_control_agent import run_governance_check
    from app.services.risk_engine import analyze_risk
    from app.services.roi_engine import analyze_roi
    from app.models.schemas import AgentResponse, SimulationResult as SimResult

    wf_id = req.workflow_id

    # ── Validate prerequisites ────────────────────────────────────────────
    wf = _workflow_cache.get(wf_id)
    if not wf:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found — call POST /api/workflow/analyze first",
        )

    agents_raw = _agent_cache.get(wf_id)
    if not agents_raw:
        raise HTTPException(
            status_code=404,
            detail="Agents not found — call POST /api/agents/generate first",
        )

    sim_raw = _sim_cache.get(wf_id)
    if not sim_raw:
        raise HTTPException(
            status_code=404,
            detail="Simulation results not found — call POST /api/simulate/run first",
        )

    try:
        agents      = [AgentResponse(**a) for a in agents_raw]
        sim_results = [SimResult(**s) for s in sim_raw]

        # ── Step 1: Governance (silent) ───────────────────────────────────
        gov_report: GovernanceReport
        if wf_id in _gov_cache:
            gov_report = GovernanceReport(**_gov_cache[wf_id])
        else:
            gov_report = await run_governance_check(
                workflow_id=wf_id,
                agents=agents,
                simulation_results=sim_results,
            )
            _gov_cache[wf_id] = gov_report.model_dump(mode="json")

        # ── Step 2: Risk analysis ─────────────────────────────────────────
        workflow_summary = f"Industry: {wf['industry']}. Description: {wf['description'][:500]}"
        agents_dicts     = [AgentResponse(**a).model_dump() for a in agents_raw]

        risk = await analyze_risk(
            workflow_id=wf_id,
            workflow_summary=workflow_summary,
            agents=agents_dicts,
            simulation_results=sim_results,
            industry=wf.get("industry", "Other"),
        )
        _risk_cache[wf_id] = risk.model_dump(mode="json")

        # ── Step 3: ROI analysis ──────────────────────────────────────────
        roi = await analyze_roi(
            workflow_id=wf_id,
            industry=wf["industry"],
            monthly_volume=wf["monthly_volume"],
            agents=agents_dicts,
        )
        _roi_cache[wf_id] = roi.model_dump(mode="json")

        # ── Step 4: Deployment plan + Executive report ────────────────────
        plan = await generate_deployment_plan(
            workflow_id=wf_id,
            risk_report=risk,
            roi_report=roi,
            simulation_results=sim_results,
        )

        success_rates  = [r.success_rate for r in sim_results]
        avg_success    = sum(success_rates) / len(success_rates) if success_rates else 0.0
        automation_score = round((avg_success * 0.7 + (1 - risk.overall_score / 100) * 0.3) * 100, 1)

        exec_report = ExecutiveReport(
            workflow_id=wf_id,
            automation_score=automation_score,
            risk_report=risk,
            roi_report=roi,
            deployment_plan=plan,
            go_no_go=plan.go_no_go,
        )
        _report_cache[wf_id] = exec_report.model_dump(mode="json")

        return PrepareReportResponse(
            workflow_id=wf_id,
            governance_summary=gov_report.summary,
            risk_report=risk,
            roi_report=roi,
            executive_report=exec_report,
            go_no_go=plan.go_no_go.value,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("prepare_report failed for %s: %s", wf_id, exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Upstream pipeline error: {exc}",
        )


# ─── Legacy individual generate endpoint (unchanged) ─────────────────────────

@router.post(
    "/generate",
    response_model=ExecutiveReport,
    summary="Generate executive report (requires prior risk + ROI calls)",
)
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
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        r = report_data
        W, H = A4

        # ── Colour palette ──────────────────────────────────────────────────
        BLACK   = colors.HexColor("#0a0a0a")
        WHITE   = colors.HexColor("#ffffff")
        GREY_BG = colors.HexColor("#f7f8fa")
        BORDER  = colors.HexColor("#e5e7eb")
        ACCENT  = colors.HexColor("#1f2328")
        MUTED   = colors.HexColor("#57606a")
        GREEN   = colors.HexColor("#1a7f37")
        YELLOW  = colors.HexColor("#9a6700")
        ORANGE  = colors.HexColor("#bc4c00")
        RED     = colors.HexColor("#a40000")

        def risk_color(score: float) -> colors.HexColor:
            if score < 30:   return GREEN
            if score < 55:   return YELLOW
            if score < 75:   return ORANGE
            return RED

        go_colors = {"GO": GREEN, "PILOT_FIRST": YELLOW, "NEEDS_CHANGES": RED}
        go_labels  = {"GO": "GO", "PILOT_FIRST": "PILOT FIRST", "NEEDS_CHANGES": "NEEDS CHANGES"}

        # ── Styles ─────────────────────────────────────────────────────────
        styles = getSampleStyleSheet()

        def S(name: str, **kw) -> ParagraphStyle:
            return ParagraphStyle(name, parent=styles["Normal"], **kw)

        title_style    = S("SQTitle",    fontSize=22, fontName="Helvetica-Bold",
                           textColor=BLACK, spaceAfter=4, leading=26)
        tagline_style  = S("SQTagline",  fontSize=10, textColor=MUTED, spaceAfter=2)
        h2_style       = S("SQH2",       fontSize=13, fontName="Helvetica-Bold",
                           textColor=BLACK, spaceBefore=14, spaceAfter=6)
        label_style    = S("SQLabel",    fontSize=8,  fontName="Helvetica-Bold",
                           textColor=MUTED, spaceAfter=1, leading=10)
        value_style    = S("SQValue",    fontSize=18, fontName="Helvetica-Bold",
                           textColor=BLACK, spaceAfter=2, leading=22)
        body_style     = S("SQBody",     fontSize=9,  textColor=ACCENT, leading=14)
        small_style    = S("SQSmall",    fontSize=8,  textColor=MUTED,  leading=12)
        bullet_style   = S("SQBullet",   fontSize=9,  textColor=ACCENT, leading=14,
                           leftIndent=10, bulletIndent=0)

        def rule() -> HRFlowable:
            return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6)

        # ── Buffer & doc ────────────────────────────────────────────────────
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2.2 * cm, leftMargin=2.2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
        )
        story = []

        # ── PAGE 1 — Cover ──────────────────────────────────────────────────
        story.append(Spacer(1, 0.8 * cm))
        story.append(Paragraph("SQUARE", S("SQCover", fontSize=42, fontName="Helvetica-Bold",
                                            textColor=BLACK, leading=46, spaceAfter=2)))
        story.append(Paragraph("Enterprise Agent Engineering Platform", tagline_style))
        story.append(Spacer(1, 0.3 * cm))
        story.append(rule())
        story.append(Paragraph("Executive Readiness Report", title_style))
        story.append(Paragraph(
            f"Workflow ID: {workflow_id[:8].upper()}  |  Generated by SQUARE AI Platform",
            small_style,
        ))
        story.append(Spacer(1, 0.5 * cm))

        go_no_go = r["go_no_go"]
        go_label = go_labels.get(go_no_go, go_no_go)
        go_col   = go_colors.get(go_no_go, MUTED)

        # Go/No-Go banner table
        banner = Table(
            [[Paragraph(go_label, S("SQBanner", fontSize=20, fontName="Helvetica-Bold",
                                    textColor=WHITE, alignment=1))]],
            colWidths=[W - 4.4 * cm],
        )
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), go_col),
            ("ROUNDEDCORNERS", [6]),
            ("TOPPADDING",    (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        story.append(banner)
        story.append(Spacer(1, 0.4 * cm))

        # Justification
        story.append(Paragraph(r["deployment_plan"]["justification"], body_style))
        story.append(Spacer(1, 0.5 * cm))
        story.append(rule())

        # ── Key Metrics grid ────────────────────────────────────────────────
        story.append(Paragraph("Key Metrics at a Glance", h2_style))

        roi = r["roi_report"]
        risk = r["risk_report"]

        metrics = [
            ("Automation Score",  f"{r['automation_score']:.1f}%",    ""),
            ("Year 1 ROI",        f"{roi['roi_percent_year1']:.0f}%",  ""),
            ("Annual Savings",    f"${roi['annual_savings']:,.0f}",    ""),
            ("Payback Period",    f"{roi['payback_period_months']:.1f} months", ""),
            ("FTE Reduction",     f"{roi['fte_reduction']:.1f}",       "FTEs"),
            ("Overall Risk",      f"{risk['overall_score']:.0f} / 100", ""),
        ]

        def metric_cell(label: str, value: str, sub: str = "") -> list:
            content = [Paragraph(label, label_style), Paragraph(value, value_style)]
            if sub:
                content.append(Paragraph(sub, small_style))
            return content

        row1 = [metric_cell(*m) for m in metrics[:3]]
        row2 = [metric_cell(*m) for m in metrics[3:]]

        col_w = (W - 4.4 * cm) / 3
        for row in [row1, row2]:
            mt = Table([row], colWidths=[col_w] * 3)
            mt.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), GREY_BG),
                ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(mt)
            story.append(Spacer(1, 0.15 * cm))

        story.append(PageBreak())

        # ── PAGE 2 — Risk + Deployment ──────────────────────────────────────
        story.append(Paragraph("Risk Breakdown", h2_style))
        story.append(rule())

        risk_rows = [["Category", "Score", "Justification"]]
        for cat in risk["categories"]:
            risk_rows.append([
                Paragraph(cat["name"], body_style),
                Paragraph(str(int(cat["score"])) + " / 100",
                          S("RC", fontSize=9, fontName="Helvetica-Bold",
                            textColor=risk_color(cat["score"]))),
                Paragraph(cat["justification"], small_style),
            ])
        risk_table = Table(risk_rows, colWidths=[3.5 * cm, 2.5 * cm, W - 4.4 * cm - 6 * cm])
        risk_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 9),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
            ("GRID",          (0, 0), (-1, -1), 0.4, BORDER),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(risk_table)
        story.append(Spacer(1, 0.4 * cm))

        story.append(Paragraph("Recommendations", h2_style))
        story.append(rule())
        for rec in risk["recommendations"]:
            story.append(Paragraph(f"• {rec}", bullet_style))
        story.append(Spacer(1, 0.4 * cm))

        story.append(Paragraph("Deployment Timeline", h2_style))
        story.append(rule())
        phase_rows = [["Phase", "Scope", "Human Oversight", "Success Criteria"]]
        for phase in r["deployment_plan"]["phases"]:
            phase_rows.append([
                Paragraph(phase["name"], body_style),
                Paragraph(f"{phase['scope_percent']}%", body_style),
                Paragraph(f"{phase['human_oversight_percent']}%", body_style),
                Paragraph(phase["success_criteria"], small_style),
            ])
        cw = (W - 4.4 * cm)
        phase_table = Table(phase_rows, colWidths=[3.5 * cm, 2 * cm, 3 * cm, cw - 8.5 * cm])
        phase_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 9),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
            ("GRID",          (0, 0), (-1, -1), 0.4, BORDER),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(phase_table)
        story.append(Spacer(1, 0.5 * cm))
        story.append(rule())
        story.append(Paragraph(
            "Generated by SQUARE — Enterprise Agent Engineering Platform. "
            "Built with IBM Bob IDE. "
            "This report is for pre-deployment evaluation only.",
            small_style,
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
