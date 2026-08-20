# -*- coding: utf-8 -*-
"""
보고서 산출물 생성
-------------------
착수보고서 "보안 점수 산출 & 보고서 산출물" 규격을 따른다.

Excel (5시트): 표지 · 대시보드요약 · 항목별상세(위험도순+조건부서식) · 조치이력 · 승인이력
PDF        : 표지 + 요약 + 상세 + 수동확인 섹션
색상 규칙   : 양호=초록 / 취약=빨강 / 수동확인(N/A)=노랑  (Excel·PDF 동일 적용)
생성 방식   : 대시보드 버튼 클릭 -> 즉시 생성·다운로드 (서버 단위 / 전체 통합 선택 가능)
"""
import io
from datetime import datetime

from flask import Blueprint, request, send_file
from flask_login import login_required

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics

from models import Server, ActionHistory, ApprovalRequest
from scoring import calc_security_level, GRADE_COLOR

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

GOOD_FILL = PatternFill("solid", fgColor="C6EFCE")
BAD_FILL = PatternFill("solid", fgColor="FFC7CE")
NA_FILL = PatternFill("solid", fgColor="FFEB9C")
HEAD_FILL = PatternFill("solid", fgColor="1F2937")
HEAD_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BASE_FONT = Font(name="Arial", size=10)
TITLE_FONT = Font(name="Arial", size=20, bold=True)
SUB_FONT = Font(name="Arial", size=11, color="555555")
THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

RISK_ORDER = {"H": 0, "M": 1, "L": 2}


def _target_servers():
    ids = request.args.getlist("server_id")
    if not ids or "all" in ids:
        return Server.query.order_by(Server.id).all(), "전체 서버"
    if len(ids) == 1:
        srv = Server.query.get_or_404(int(ids[0]))
        return [srv], srv.hostname
    servers = Server.query.filter(Server.id.in_([int(i) for i in ids])).order_by(Server.id).all()
    label = ", ".join(s.hostname for s in servers) if len(servers) <= 4 else f"선택 서버 {len(servers)}대"
    return servers, label


def _style_header(ws, row, headers, widths):
    for idx, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=idx, value=h)
        c.font = HEAD_FONT
        c.fill = HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER
        ws.column_dimensions[get_column_letter(idx)].width = widths[idx - 1]


def _result_fill(result):
    if result == "취약":
        return BAD_FILL
    if result == "N/A":
        return NA_FILL
    return GOOD_FILL


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
@reports_bp.route("/excel")
@login_required
def excel_report():
    servers, scope_label = _target_servers()
    wb = Workbook()

    # 1) 표지 -----------------------------------------------------------
    cover = wb.active
    cover.title = "표지"
    cover.sheet_view.showGridLines = False
    cover["B3"] = "KISA U-01~U-67 다중 서버 보안 자동화 플랫폼"
    cover["B3"].font = Font(name="Arial", size=13, color="888888")
    cover["B5"] = "서버 취약점 진단 결과 보고서"
    cover["B5"].font = TITLE_FONT
    cover["B7"] = f"대상 범위 : {scope_label}"
    cover["B7"].font = SUB_FONT
    cover["B8"] = f"생성 일시 : {datetime.now():%Y-%m-%d %H:%M}"
    cover["B8"].font = SUB_FONT
    cover["B9"] = "생성 방식 : 대시보드 버튼 클릭 즉시 생성"
    cover["B9"].font = SUB_FONT
    cover["B11"] = "색상 규칙 : 양호=초록 · 취약=빨강 · 수동확인(N/A)=노랑"
    cover["B11"].font = SUB_FONT
    for col, w in zip("ABCDEFG", [4, 60, 16, 16, 16, 16, 16]):
        cover.column_dimensions[col].width = w

    # 2) 대시보드요약 ------------------------------------------------------
    ws = wb.create_sheet("대시보드요약")
    ws["B2"] = "서버별 보안 수준 요약"
    ws["B2"].font = Font(name="Arial", size=13, bold=True)
    headers = ["호스트명", "IP", "OS", "업무명", "보안점수", "등급", "취약 건수", "전체 항목수"]
    widths = [16, 16, 18, 22, 12, 10, 12, 12]
    _style_header(ws, 4, headers, widths)

    row = 5
    total_score = 0
    for srv in servers:
        results = srv.latest_results()
        level, grade, total, identified = calc_security_level(results)
        vuln_cnt = sum(1 for r in results if r.result == "취약")
        applicable = sum(1 for r in results if r.result != "N/A")
        ws.cell(row=row, column=1, value=srv.hostname).border = BORDER
        ws.cell(row=row, column=2, value=srv.ip).border = BORDER
        ws.cell(row=row, column=3, value=srv.os_label).border = BORDER
        ws.cell(row=row, column=4, value=srv.business_name).border = BORDER
        sc = ws.cell(row=row, column=5, value=level)
        sc.border = BORDER
        sc.fill = GOOD_FILL if grade in ("우수", "양호") else (NA_FILL if grade == "보통" else BAD_FILL)
        ws.cell(row=row, column=6, value=grade).border = BORDER
        ws.cell(row=row, column=7, value=vuln_cnt).border = BORDER
        ws.cell(row=row, column=8, value=applicable).border = BORDER
        total_score += level
        row += 1

    avg_row = row + 1
    ws.cell(row=avg_row, column=4, value="전체 평균").font = Font(name="Arial", bold=True)
    avg_cell = ws.cell(row=avg_row, column=5,
                        value=f"=ROUND(AVERAGE(E5:E{row-1}),1)" if row > 5 else 0)
    avg_cell.font = Font(name="Arial", bold=True)

    # 카테고리별 준수율
    cat_row = avg_row + 3
    ws.cell(row=cat_row, column=2, value="카테고리별 준수율").font = Font(name="Arial", size=12, bold=True)
    cat_headers = ["카테고리", "전체 항목수(서버합산)", "취약 건수", "준수율(%)"]
    _style_header(ws, cat_row + 1, cat_headers, [24, 20, 14, 14])
    cat_stats = {}
    for srv in servers:
        for r in srv.latest_results():
            if r.result == "N/A":
                continue
            cat = r.check_item.category
            cat_stats.setdefault(cat, [0, 0])
            cat_stats[cat][0] += 1
            if r.result == "취약":
                cat_stats[cat][1] += 1
    r_i = cat_row + 2
    for cat, (tot, vuln) in cat_stats.items():
        rate = round((1 - vuln / tot) * 100, 1) if tot else 0
        ws.cell(row=r_i, column=2, value=cat).border = BORDER
        ws.cell(row=r_i, column=3, value=tot).border = BORDER
        ws.cell(row=r_i, column=4, value=vuln).border = BORDER
        rc = ws.cell(row=r_i, column=5, value=rate)
        rc.border = BORDER
        rc.fill = GOOD_FILL if rate >= 80 else (NA_FILL if rate >= 60 else BAD_FILL)
        r_i += 1

    # 3) 항목별상세 (위험도순 + 조건부서식) ---------------------------------
    ws2 = wb.create_sheet("항목별상세")
    headers2 = ["서버", "항목코드", "카테고리", "점검항목", "위험도", "진단결과", "배점",
                "현재설정(취약시)", "조치권고", "조치방식"]
    widths2 = [14, 10, 20, 34, 8, 10, 8, 40, 40, 10]
    _style_header(ws2, 1, headers2, widths2)

    all_rows = []
    for srv in servers:
        for r in srv.latest_results():
            ci = r.check_item
            all_rows.append((srv, r, ci))
    all_rows.sort(key=lambda x: (RISK_ORDER.get(x[2].risk_level, 9), x[0].hostname, x[2].order_no))

    r_i = 2
    for srv, r, ci in all_rows:
        remediation_label = ("수동" if r.remediation_type == "manual" else "자동") if r.result == "취약" else ""
        vals = [srv.hostname, ci.code, ci.category, ci.name, ci.risk_level, r.result, ci.weight,
                r.current_setting or "", r.recommendation or "", remediation_label]
        for col, v in enumerate(vals, start=1):
            cell = ws2.cell(row=r_i, column=col, value=v)
            cell.font = BASE_FONT
            cell.border = BORDER
            cell.alignment = Alignment(wrap_text=(col in (8, 9)), vertical="top")
            if col == 6:
                cell.fill = _result_fill(r.result)
        r_i += 1
    ws2.freeze_panes = "A2"

    # 4) 조치이력 --------------------------------------------------------
    ws3 = wb.create_sheet("조치이력")
    headers3 = ["수행일시", "서버", "항목코드", "항목명", "이전결과", "이후결과",
                "이전점수", "이후점수", "수행자", "백업경로"]
    widths3 = [18, 14, 10, 30, 10, 10, 10, 10, 26, 34]
    _style_header(ws3, 1, headers3, widths3)
    server_ids = {s.id for s in servers}
    hist = (ActionHistory.query.order_by(ActionHistory.performed_at.desc()).all())
    r_i = 2
    for h in hist:
        if h.server_id not in server_ids:
            continue
        vals = [h.performed_at.strftime("%Y-%m-%d %H:%M"), h.server.hostname, h.check_item.code,
                h.check_item.name, h.before_result, h.after_result, h.before_score, h.after_score,
                h.performed_by, h.backup_path]
        for col, v in enumerate(vals, start=1):
            cell = ws3.cell(row=r_i, column=col, value=v)
            cell.font = BASE_FONT
            cell.border = BORDER
        r_i += 1

    # 5) 승인이력 --------------------------------------------------------
    ws4 = wb.create_sheet("승인이력")
    headers4 = ["요청일시", "서버", "항목코드", "항목명", "요청자", "상태", "승인자",
                "결정일시", "거부사유", "실행일시"]
    widths4 = [18, 14, 10, 30, 16, 10, 16, 18, 30, 18]
    _style_header(ws4, 1, headers4, widths4)
    apr = ApprovalRequest.query.order_by(ApprovalRequest.requested_at.desc()).all()
    r_i = 2
    status_label = {"pending": "대기", "approved": "승인", "rejected": "거부"}
    for a in apr:
        if a.server_id not in server_ids:
            continue
        vals = [a.requested_at.strftime("%Y-%m-%d %H:%M"), a.server.hostname, a.check_item.code,
                a.check_item.name, a.requested_by, status_label.get(a.status, a.status),
                a.approver or "", a.decided_at.strftime("%Y-%m-%d %H:%M") if a.decided_at else "",
                a.reject_reason or "", a.executed_at.strftime("%Y-%m-%d %H:%M") if a.executed_at else ""]
        for col, v in enumerate(vals, start=1):
            cell = ws4.cell(row=r_i, column=col, value=v)
            cell.font = BASE_FONT
            cell.border = BORDER
            if col == 6:
                cell.fill = {"대기": NA_FILL, "승인": GOOD_FILL, "거부": BAD_FILL}.get(v, PatternFill())
        r_i += 1

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"보안진단_보고서_{scope_label}_{datetime.now():%Y%m%d_%H%M}.xlsx".replace(" ", "")
    return send_file(buf, as_attachment=True, download_name=fname,
                      mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------------------
# PDF (markdown -> HTML -> weasyprint 대신, 배포 편의를 위해 reportlab으로 직접 생성)
# ---------------------------------------------------------------------------
@reports_bp.route("/pdf")
@login_required
def pdf_report():
    servers, scope_label = _target_servers()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             topMargin=18 * mm, bottomMargin=16 * mm,
                             leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleKo", parent=styles["Title"], fontSize=20, leading=24)
    h2_style = ParagraphStyle("H2Ko", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6)
    normal = styles["Normal"]

    story = []
    story.append(Paragraph("서버 취약점 진단 결과 보고서", title_style))
    story.append(Paragraph("KISA U-01~U-67 다중 서버 보안 자동화 플랫폼", normal))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"대상 범위: {scope_label}", normal))
    story.append(Paragraph(f"생성 일시: {datetime.now():%Y-%m-%d %H:%M}", normal))
    story.append(Spacer(1, 6 * mm))

    # 요약 표
    story.append(Paragraph("1. 요약", h2_style))
    data = [["호스트명", "OS", "보안점수", "등급", "취약 건수"]]
    for srv in servers:
        results = srv.latest_results()
        level, grade, total, identified = calc_security_level(results)
        vuln_cnt = sum(1 for r in results if r.result == "취약")
        data.append([srv.hostname, srv.os_label, str(level), grade, str(vuln_cnt)])
    t = Table(data, colWidths=[32 * mm, 30 * mm, 26 * mm, 24 * mm, 26 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    # 상세 표(취약 항목만, 위험도순) - 지면 관계상 취약 항목 위주로 구성
    story.append(Paragraph("2. 상세 - 취약 항목 (위험도순)", h2_style))
    detail_data = [["서버", "코드", "항목명", "위험도", "결과"]]
    rows = []
    for srv in servers:
        for r in srv.latest_results():
            if r.result != "취약":
                continue
            rows.append((srv, r))
    rows.sort(key=lambda x: (RISK_ORDER.get(x[1].check_item.risk_level, 9), x[0].hostname))
    for srv, r in rows:
        detail_data.append([srv.hostname, r.check_item.code, r.check_item.name,
                             r.check_item.risk_level, r.result])
    if len(detail_data) == 1:
        detail_data.append(["-", "-", "취약 항목 없음", "-", "-"])
    t2 = Table(detail_data, colWidths=[24 * mm, 18 * mm, 66 * mm, 16 * mm, 16 * mm])
    style2 = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
    ]
    for i in range(1, len(detail_data)):
        style2.append(("BACKGROUND", (4, i), (4, i), colors.HexColor("#FFC7CE")))
    t2.setStyle(TableStyle(style2))
    story.append(t2)
    story.append(Spacer(1, 6 * mm))

    # 수동확인 섹션
    story.append(Paragraph("3. 수동 확인 필요 항목 (N/A)", h2_style))
    na_rows = []
    for srv in servers:
        for r in srv.latest_results():
            if r.result == "N/A":
                na_rows.append((srv, r))
    if na_rows:
        na_data = [["서버", "코드", "항목명"]] + [
            [srv.hostname, r.check_item.code, r.check_item.name] for srv, r in na_rows
        ]
        t3 = Table(na_data, colWidths=[30 * mm, 20 * mm, 90 * mm])
        t3.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFEB9C")),
        ]))
        story.append(t3)
    else:
        story.append(Paragraph("수동 확인이 필요한 N/A 항목이 없습니다.", normal))

    doc.build(story)
    buf.seek(0)
    fname = f"보안진단_보고서_{scope_label}_{datetime.now():%Y%m%d_%H%M}.pdf".replace(" ", "")
    return send_file(buf, as_attachment=True, download_name=fname, mimetype="application/pdf")
