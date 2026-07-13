// PAPER.md -> PAPER.docx  (matches the "Formatted" template: running header, styled title block,
// WORKING PAPER label, topics line, Contents/TOC, styled headings, page numbers, justified body)
// ALL FONT COLOR BLACK (000000).
const fs = require('fs');
const D = require('docx');
const { Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell, WidthType,
        BorderStyle, LineRuleType, Header, Footer, PageNumber, PageBreak, TableOfContents, HeadingLevel } = D;

const SERIF = 'Cambria', SANS = 'Calibri', MONO = 'Consolas', BLACK = '000000';
const md = fs.readFileSync(process.argv[2] || 'PAPER.md', 'utf8');
const lines = md.split('\n');

function runs(text, opts = {}) {
  const base = { font: SERIF, size: 22, color: BLACK, ...opts };
  const out = []; const re = /(\*\*(.+?)\*\*|(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|`([^`]+)`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ ...base, text: text.slice(last, m.index) }));
    if (m[2] !== undefined) out.push(new TextRun({ ...base, text: m[2], bold: true }));
    else if (m[3] !== undefined) out.push(new TextRun({ ...base, text: m[3], italics: true }));
    else if (m[4] !== undefined) out.push(new TextRun({ ...base, text: m[4], font: MONO, size: 19 }));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(new TextRun({ ...base, text: text.slice(last) }));
  if (!out.length) out.push(new TextRun({ ...base, text: '' }));
  return out;
}

const LN = { line: 276, lineRule: LineRuleType.AUTO };  // 1.15 spacing
const body = (t) => new Paragraph({ children: runs(t), alignment: AlignmentType.JUSTIFIED, spacing: { ...LN, after: 140 } });
const B = { style: BorderStyle.SINGLE, size: 4, color: '999999' };
const cb = { top: B, bottom: B, left: B, right: B };

function makeTable(rows) {
  const nc = rows[0].length, total = 9360, cw = Math.floor(total / nc);
  return new Table({ columnWidths: Array(nc).fill(cw), width: { size: total, type: WidthType.DXA },
    rows: rows.map((cells, ri) => new TableRow({ children: cells.map((c, ci) => new TableCell({
      width: { size: cw, type: WidthType.DXA }, borders: cb, margins: { top: 20, bottom: 20, left: 90, right: 90 },
      children: [new Paragraph({ alignment: ci === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT,
        spacing: { line: 240, lineRule: LineRuleType.AUTO }, children: runs(c.trim(), { size: 20, bold: ri === 0 }) })] })) })) });
}

// centered short rule (paragraph bottom border with wide indents)
const rule = new Paragraph({ alignment: AlignmentType.CENTER, indent: { left: 2600, right: 2600 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLACK, space: 6 } }, spacing: { before: 60, after: 200 },
  children: [new TextRun({ text: '', size: 2 })] });

const children = [];
let i = 0, seenSection = false;
while (i < lines.length) {
  const raw = lines[i], t = raw.trim();

  if (t.startsWith('```')) { i++;
    while (i < lines.length && !lines[i].trim().startsWith('```')) {
      children.push(new Paragraph({ spacing: { line: 240, lineRule: LineRuleType.AUTO },
        children: [new TextRun({ text: lines[i] || ' ', font: MONO, size: 18, color: BLACK })] })); i++; }
    i++; continue; }

  if (t.startsWith('|') && t.endsWith('|')) { const tb = [];
    while (i < lines.length && lines[i].trim().startsWith('|')) {
      if (!/^[\s:|-]+$/.test(lines[i].replace(/\|/g, '')))
        tb.push(lines[i].trim().replace(/^\|/, '').replace(/\|$/, '').split('|')); i++; }
    if (tb.length) { children.push(makeTable(tb)); children.push(new Paragraph({ spacing: { after: 140 }, children: [] })); }
    continue; }

  if (t === '') { i++; continue; }

  if (t.startsWith('# ')) {                          // TITLE PAGE
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 240, after: 120 },
      children: runs(t.slice(2), { font: SERIF, bold: true, size: 32 }) }));
  } else if (!seenSection && t.startsWith('**')) {   // subtitle
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
      children: runs(t.replace(/^\*\*|\*\*$/g, ''), { italics: true, size: 24 }) }));
  } else if (!seenSection && /Parv Mehndiratta/.test(t)) {  // byline -> then WORKING PAPER block + TOC
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: runs(t.replace(/^\*|\*$/g, ''), { bold: true, size: 22 }) }));
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
      children: [new TextRun({ text: 'WORKING PAPER', bold: true, allCaps: true, size: 20, font: SANS, color: BLACK, characterSpacing: 30 })] }));
    children.push(rule);
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
      children: [new TextRun({ text: 'Quantitative Finance   •   Multiple Testing   •   LLM Strategy Search', italics: true, size: 21, font: SERIF, color: BLACK })] }));
    children.push(new Paragraph({ children: [new PageBreak()] }));
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: 'Contents', font: SANS, bold: true, size: 28, color: BLACK })] }));
    children.push(new TableOfContents('Contents', { hyperlinks: false, headingStyleRange: '1-2' }));
    children.push(new Paragraph({ children: [new PageBreak()] }));
  } else if (!seenSection && t.startsWith('*')) {    // keywords/JEL line
    children.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 160, ...LN },
      children: runs(t.replace(/^\*|\*$/g, ''), { italics: true, size: 21 }) }));
  } else if (t.startsWith('### ')) {
    seenSection = true;
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t.slice(4), font: SANS, bold: true, size: 24, color: BLACK })] }));
  } else if (t.startsWith('## ')) {
    seenSection = true;
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t.slice(3), font: SANS, bold: true, size: 28, color: BLACK })] }));
  } else if (t.startsWith('> ')) {
    children.push(new Paragraph({ indent: { left: 500 }, spacing: { ...LN, after: 120 }, children: runs(t.slice(2), { italics: true }) }));
  } else if (/^[-*]\s+/.test(t)) {
    children.push(new Paragraph({ bullet: { level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { ...LN, after: 60 }, children: runs(t.replace(/^[-*]\s+/, '')) }));
  } else if (/^\d+\.\s+/.test(t)) {
    children.push(new Paragraph({ indent: { left: 360, hanging: 360 }, alignment: AlignmentType.JUSTIFIED, spacing: { ...LN, after: 60 }, children: runs(t) }));
  } else {
    children.push(body(t));
  }
  i++;
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: SERIF, size: 22, color: BLACK } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: SANS, size: 28, bold: true, color: BLACK }, paragraph: { spacing: { before: 300, after: 100 }, keepNext: true } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: SANS, size: 24, bold: true, color: BLACK }, paragraph: { spacing: { before: 220, after: 60 }, keepNext: true } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ spacing: { after: 120 },
      children: [new TextRun({ text: 'MORE STRATEGIES, SAME ZERO', allCaps: true, bold: true, size: 16, font: SANS, color: BLACK })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ children: [PageNumber.CURRENT], size: 20, font: SERIF, color: BLACK })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync(process.argv[3] || 'PAPER.docx', b); console.log('wrote', process.argv[3] || 'PAPER.docx', b.length); });
