#!/usr/bin/env python3.14
"""Build a clean submission PDF from PAPER.md + the two headline figures.
Route: markdown -> styled HTML (figures embedded base64) -> Chrome headless --print-to-pdf.
Output: PAPER.pdf in this directory."""
import base64, subprocess, sys, os
from pathlib import Path
import markdown

HERE = Path(__file__).parent
md_text = (HERE / "PAPER.md").read_text()

# Embed figures as base64 so Chrome renders them regardless of cwd.
def data_uri(fname, mime):
    p = HERE / fname
    if not p.exists():
        return None
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"

fig_head = data_uri("fig_headline.png", "image/png")
fig_ver = data_uri("fig_verification.png", "image/png")
fig_eval = data_uri("fig_evaluator_overfit.svg", "image/svg+xml")

# Insert a Figures block right after the Abstract section (before "## 1.").
figs_html = "\n\n<div class='figures'>\n"
if fig_head:
    figs_html += f"<figure><img src='{fig_head}'/><figcaption><b>Figure 1.</b> Headline: naive best-of-N Sharpe climbs with N on every market including pure noise and the real S&amp;P 500, while the deflated worst-regime gate holds survivors at zero on real data for all N.</figcaption></figure>\n"
if fig_ver:
    figs_html += f"<figure><img src='{fig_ver}'/><figcaption><b>Figure 2.</b> Verification: the gate recovers a strong planted edge (survivors grow with N) yet rejects moderate real edges, and the real-market zero is robust to the corrected, weaker worst-of-regimes bar.</figcaption></figure>\n"
if fig_eval:
    figs_html += f"<figure><img src='{fig_eval}'/><figcaption><b>Figure 3.</b> Overfitting the judge: as the number of tuned candidates grows, the optimized evaluator score climbs an order of magnitude above true quality (which rises only marginally); an independent-judge ensemble restores calibration.</figcaption></figure>\n"
figs_html += "</div>\n\n"

marker = "## 1. Introduction and research question"
if marker in md_text:
    md_text = md_text.replace(marker, figs_html + marker, 1)
else:
    md_text = md_text + figs_html

html_body = markdown.markdown(
    md_text,
    extensions=["extra", "tables", "fenced_code", "toc", "sane_lists"],
)

CSS = """
@page { size: letter; margin: 0.85in 0.9in; }
body { font-family: 'Georgia','Times New Roman',serif; font-size: 10.5pt; line-height: 1.45; color:#111; max-width: 100%; }
h1 { font-size: 19pt; line-height:1.2; margin: 0 0 6pt; }
h2 { font-size: 14pt; margin: 20pt 0 6pt; border-bottom:1px solid #ccc; padding-bottom:3px; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; }
h4 { font-size: 10.8pt; margin: 10pt 0 3pt; }
p, li { text-align: justify; }
code, pre { font-family: 'Menlo','Courier New',monospace; font-size: 9pt; background:#f5f5f5; }
pre { padding:8px; border-radius:4px; overflow-x:auto; white-space:pre-wrap; }
table { border-collapse: collapse; font-size: 9pt; margin: 8pt 0; width:100%; }
th, td { border:1px solid #bbb; padding:3px 6px; text-align:left; }
th { background:#efefef; }
em { color:#222; }
blockquote { border-left:3px solid #ccc; margin:8pt 0; padding:2pt 10pt; color:#333; }
.figures figure { margin: 14pt 0; text-align:center; page-break-inside: avoid; }
.figures img { max-width: 100%; height:auto; border:1px solid #ddd; }
figcaption { font-size: 9pt; color:#333; text-align:left; margin-top:4px; }
hr { border:none; border-top:1px solid #ddd; margin:14pt 0; }
"""

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>{CSS}</style></head><body>{html_body}</body></html>"""

html_path = HERE / "PAPER_render.html"
html_path.write_text(html)

chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
pdf_path = HERE / "PAPER.pdf"
subprocess.run([
    chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
    f"--print-to-pdf={pdf_path}", f"file://{html_path}"
], check=True, capture_output=True)
print(f"OK -> {pdf_path} ({pdf_path.stat().st_size//1024} KB)")
