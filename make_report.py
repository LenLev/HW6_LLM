"""Render the short report from verified metrics and experiment notes."""
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak

ROOT = Path(__file__).resolve().parent
rows = json.loads((ROOT/"metrics.json").read_text(encoding="utf-8"))
notes = json.loads((ROOT/"report_notes.json").read_text(encoding="utf-8"))
assert all(r["complete"] for r in rows), "Do not report unfinished runs"
fixed = [r for r in rows if r["mode"] == "fixed"]
baseline = next(r for r in fixed if r["config"] == "baseline")
best = next(r for r in fixed if r["config"] == notes["best"])
loads = sorted([r for r in rows if r["mode"] == "load" and r["config"] == notes["best"]], key=lambda r:r["rpm"])
passing = [r for r in loads if r["p90_s"] < 15 and r["errors"] == 0]
limit = max(passing, key=lambda r:r["rpm"])
assert any(r["rpm"] > limit["rpm"] and r["p90_s"] >= 15 for r in loads)
if Path("C:/Windows/Fonts/arial.ttf").exists():
    regular, bold = "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"
else:
    regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
pdfmetrics.registerFont(TTFont("Arial", regular))
pdfmetrics.registerFont(TTFont("ArialBold", bold))
body = ParagraphStyle("body", fontName="Arial", fontSize=10, leading=13, spaceAfter=6)
small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, spaceAfter=0)
heading = ParagraphStyle("heading", parent=body, fontName="ArialBold", fontSize=12, leading=15, spaceBefore=8, spaceAfter=7)
title = ParagraphStyle("title", parent=heading, fontSize=17, leading=21, spaceBefore=0)
story = []
markdown = []

def paragraph(text, style=body):
    assert not any(c in text for c in "—–→"), text
    story.append(Paragraph(escape(text), style))
    markdown.append(text + "\n")

def table(headers, data, widths):
    cells = [[Paragraph(escape(str(v)), small) for v in row] for row in [headers, *data]]
    result = Table(cells, colWidths=[w*mm for w in widths], repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eeeeee")),
        ("LINEBELOW", (0,0), (-1,0), .6, colors.grey),
        ("LINEBELOW", (0,1), (-1,-1), .25, colors.HexColor("#cccccc")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(result)
    story.append(Spacer(1, 6))
    markdown.extend(["| " + " | ".join(map(str, headers)) + " |", "| " + " | ".join(["---"]*len(headers)) + " |"])
    markdown.extend("| " + " | ".join(map(str,row)) + " |" for row in data)
    markdown.append("")

def figure(name, width, height):
    story.append(Image(str(ROOT/"figures"/name), width=width*mm, height=height*mm))
    markdown.append(f"![График](figures/{name})\n")

paragraph("ДЗ 6. Ускорение инференса", title)
paragraph("Qwen3-8B на одной A100 80 GB (GPU 1). vLLM 0.22.0, AIPerf 0.13.0. Thinking выключен, temperature=0, seed=42, max_tokens=512. Данные не изменялись.")
paragraph("1. Ускорение при 120 RPM", heading)
paragraph("Каждая конфигурация обработала все 640 запросов. Прогрев: 40 запросов. Prefix cache очищался до прогрева и после теста; при смене конфигурации сервер перезапускался. S = Mean бейзлайна / Mean конфигурации.")
data = [[r["config"], notes["parameters"][r["config"]], f"{r['mean_s']:.2f}", f"{r['p90_s']:.2f}", f"{baseline['mean_s']/r['mean_s']:.2f}"] for r in fixed]
table(["Конфигурация", "Изменения", "Mean, с", "P90, с", "S"], data, [30, 82, 21, 21, 20])
paragraph(notes["optimization"])
paragraph("2. Спекдекод и нагрузка", heading)
paragraph("Сравниваются одинаковые настройки 64 seq / 2048 tokens, с EAGLE-3 и без него. При каждом RPM - те же 640 запросов. Справа: P90 без спекдека / P90 со спекдеком. Точка 120 RPM взята из первого этапа.")
figure("speculation.png", 174, 56.34)
paragraph(notes["speculation"])
story.append(PageBreak())
paragraph("3. Максимальная нагрузка", heading)
paragraph(f"Конфигурация: {notes['best']}. Каждый тест: 300 секунд подачи запросов через load_test.sh, затем ожидание ответов. Условие: P90 E2E < 15 секунд.")
figure("capacity.png", 174, 72.5)
table(["RPM", "Запросов", "Mean, с", "P90, с", "Ошибок", "SLA"],
      [[r["rpm"],r["success"],f"{r['mean_s']:.2f}",f"{r['p90_s']:.2f}",r["errors"],"да" if r["p90_s"]<15 and r["errors"]==0 else "нет"] for r in loads],
      [24,32,30,30,28,30])
paragraph(f"Максимум среди проверенных нагрузок: {limit['rpm']} RPM ({limit['rpm']/60:.2f} RPS), P90 = {limit['p90_s']:.2f} с.")
paragraph(notes["capacity"])
paragraph(notes["limitations"])
paragraph("Все конфигурации - в configs/, исходные результаты AIPerf - в results/, полная таблица - metrics.csv. Графики строятся скриптом plot_results.py; команды экспериментов сохранены в README.md.")
SimpleDocTemplate(str(ROOT/"report.pdf"), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm,
                  title="ДЗ 6. Ускорение инференса", author="").build(story)
(ROOT/"report.md").write_text("\n".join(markdown), encoding="utf-8")
print(ROOT/"report.pdf")
