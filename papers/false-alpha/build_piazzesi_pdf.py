#!/usr/bin/env python3.14
"""Build a submission PDF in the style of a Piazzesi/NBER economics working paper.
Route: PAPER.md -> academic-styled HTML (Times serif, centered title block, indented
abstract, justified 1.5-spaced first-line-indented body, booktabs tables, no TOC,
centered page numbers) -> Chrome headless --print-to-pdf.
Output: PAPER_piazzesi.pdf in this directory."""
import base64, subprocess, re
from pathlib import Path
import markdown

HERE = Path(__file__).parent
md = (HERE / "PAPER.md").read_text()
lines = md.split("\n")

# ---- parse front matter ----
def first(pred):
    for ln in lines:
        if pred(ln.strip()):
            return ln.strip()
    return ""

title = first(lambda t: t.startswith("# "))[2:].strip()
subtitle = first(lambda t: t.startswith("**") and t.endswith("**")).strip("*").strip()
byline = first(lambda t: "Parv Mehndiratta" in t and "Working paper" in t)
mdate = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", byline)
date = mdate.group(0) if mdate else "2026"
keywords = first(lambda t: t.startswith("*Keywords")).strip("*").strip()

# abstract = lines between "## Abstract" and the next "## " heading
abs, grab = [], False
for ln in lines:
    s = ln.strip()
    if s == "## Abstract":
        grab = True; continue
    if grab and s.startswith("## "):
        break
    if grab:
        abs.append(ln)
abstract_md = "\n".join(abs).strip()

# body = from "## 1." onward
body_start = next(i for i, ln in enumerate(lines) if re.match(r"^## 1\.", ln.strip()))
body_md = "\n".join(lines[body_start:])

# ---- figures (embedded), placed at the top of the Results section ----
def data_uri(fname, mime):
    p = HERE / fname
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}" if p.exists() else None

fig_head = data_uri("fig_headline.png", "image/png")
fig_ver = data_uri("fig_verification.png", "image/png")
fig_eval = data_uri("fig_evaluator_overfit.svg", "image/svg+xml")
figs = "\n\n<div class='figures'>\n"
if fig_head:
    figs += f"<figure><img src='{fig_head}'/><figcaption><b>Figure 1.</b> Naive best-of-N Sharpe climbs with N on every market including pure noise and the real S&amp;P 500, while the deflated worst-regime gate holds survivors at zero on real data for all N.</figcaption></figure>\n"
if fig_ver:
    figs += f"<figure><img src='{fig_ver}'/><figcaption><b>Figure 2.</b> The gate recovers a strong planted edge (survivors grow with N) yet rejects moderate real edges; the real-market zero is robust to the corrected, weaker worst-of-regimes bar.</figcaption></figure>\n"
if fig_eval:
    figs += f"<figure><img src='{fig_eval}'/><figcaption><b>Figure 3.</b> As the number of tuned candidates grows, the optimized evaluator score climbs an order of magnitude above true quality; an independent-judge ensemble restores calibration.</figcaption></figure>\n"
figs += "</div>\n\n"
if "## 4. Results" in body_md:
    body_md = body_md.replace("## 4. Results", "## 4. Results\n" + figs, 1)

# ---- normalize list spacing: markdown needs a blank line before a list block ----
def fix_lists(t):
    out, ls = [], t.split("\n")
    item = lambda s: bool(re.match(r"(-|\*|\d+\.)\s", s.lstrip()))
    for i, ln in enumerate(ls):
        if item(ln) and i > 0 and ls[i-1].strip() and not item(ls[i-1]):
            out.append("")
        out.append(ln)
    return "\n".join(out)

body_md = fix_lists(body_md)

# ---- render markdown -> html ----
mdx = ["extra", "tables", "fenced_code", "sane_lists"]
abstract_html = markdown.markdown(abstract_md, extensions=mdx)
keywords_html = markdown.markdown(keywords, extensions=mdx)
body_html = markdown.markdown(body_md, extensions=mdx)

titleblock = f"""
<div class="titleblock">
  <div class="doctitle">{title}</div>
  <div class="subtitle">{subtitle}</div>
  <div class="author">Parv Mehndiratta</div>
  <div class="affil">Independent Researcher</div>
  <div class="date">{date}</div>
</div>
<div class="abstract">
  <div class="abshead">Abstract</div>
  {abstract_html}
  <div class="keywords">{keywords_html}</div>
</div>
<div class="body">
{body_html}
</div>
"""

CSS = """
@page { size: letter; margin: 1in 1.25in; }
html { font-size: 12pt; }
body { font-family: 'Times New Roman', Times, serif; font-size: 12pt; line-height: 1.5; color:#000; }

/* ---- title block ---- */
.titleblock { text-align:center; margin: 0.35in 0 0.45in; }
.doctitle { font-size: 21pt; line-height:1.25; margin: 0 auto 14pt; max-width: 90%; }
.subtitle { font-size: 12.5pt; font-style:italic; line-height:1.35; margin: 0 auto 22pt; max-width: 82%; }
.author { font-size: 13pt; margin: 0; }
.affil  { font-size: 12pt; margin: 1pt 0 16pt; }
.date   { font-size: 12pt; margin: 0 0 6pt; }

/* ---- abstract (indented, narrower than body) ---- */
.abstract { margin: 0.35in 0.55in 0.5in; }
.abshead { text-align:center; font-weight:bold; font-size:12pt; margin: 0 0 8pt; }
.abstract p { text-align:justify; text-indent: 1.6em; line-height:1.5; margin:0; }
.keywords { margin-top: 12pt; font-size: 10.5pt; }
.keywords p { text-align:justify; text-indent:0; margin:0; }

/* ---- body ---- */
.body p { text-align:justify; text-indent: 1.6em; margin: 0; line-height: 1.5; }
.body h2, .body h3, .body h4 { text-align:left; }
.body h2 { font-size: 14.5pt; font-weight: bold; margin: 22pt 0 8pt; page-break-after: avoid; }
.body h3 { font-size: 12.5pt; font-weight: bold; margin: 16pt 0 5pt; page-break-after: avoid; }
.body h4 { font-size: 12pt; font-weight: bold; font-style:italic; margin: 12pt 0 4pt; }
/* first paragraph after a heading is not indented (LaTeX convention) */
.body h2 + p, .body h3 + p, .body h4 + p { text-indent: 0; }
.body ul, .body ol { margin: 4pt 0 8pt; padding-left: 1.6em; }
.body li { text-align:justify; line-height:1.45; margin: 1pt 0; }

/* ---- displayed quotes (research questions) ---- */
blockquote { margin: 10pt 0.5in; font-style: italic; text-align:justify; line-height:1.45; }
blockquote p { text-indent:0; margin:0; }

/* ---- code / reproducibility ---- */
pre { font-family:'Courier New',monospace; font-size: 9.2pt; line-height:1.3;
      background:#f6f6f6; padding:8px 10px; white-space:pre-wrap; border-radius:3px; }
code { font-family:'Courier New',monospace; font-size: 0.88em; }
p code, li code { background:#f2f2f2; padding:0 2px; }

/* ---- booktabs-style tables ---- */
table { border-collapse: collapse; margin: 12pt auto; font-size: 10.5pt; line-height:1.25; }
table { border-top: 1.4px solid #000; border-bottom: 1.4px solid #000; }
thead th { border-bottom: 1px solid #000; font-weight:bold; }
th, td { padding: 3px 12px; text-align: right; }
th:first-child, td:first-child { text-align: left; }

/* ---- figures ---- */
.figures figure { margin: 14pt 0; text-align:center; page-break-inside: avoid; }
.figures img { max-width: 100%; height:auto; }
figcaption { font-size: 10.5pt; text-align:justify; margin-top:5px; line-height:1.35; }

hr { border:none; border-top:0; margin:0; }
em { font-style: italic; }
"""

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{titleblock}</body></html>"""
html_path = HERE / "PAPER_piazzesi.html"
html_path.write_text(html)

chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
pdf_path = HERE / "PAPER_piazzesi.pdf"
subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path}", f"file://{html_path}"],
               check=True, capture_output=True)

# ---- stamp centered page numbers at the bottom (Piazzesi/NBER convention) ----
try:
    import io, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(pdf_path))
    buf = io.BytesIO()
    with PdfPages(buf) as pp:
        for i in range(1, len(reader.pages) + 1):
            fig = plt.figure(figsize=(8.5, 11))
            fig.text(0.5, 0.055, str(i), ha="center", va="center", fontsize=11,
                     family="serif", color="black")
            pp.savefig(fig, transparent=True); plt.close(fig)
    buf.seek(0)
    overlay = PdfReader(buf)
    writer = PdfWriter()
    for i, pg in enumerate(reader.pages):
        pg.merge_page(overlay.pages[i]); writer.add_page(pg)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    print(f"OK -> {pdf_path} ({pdf_path.stat().st_size//1024} KB, {len(reader.pages)} pp, page numbers stamped)")
except Exception as e:
    print(f"OK -> {pdf_path} ({pdf_path.stat().st_size//1024} KB) [page-number step skipped: {e}]")
