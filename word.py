"""Livrable Markdown → document Word (.docx) avec de vraies notes de bas de page, sans rien installer.

Chaque citation [n] dont la référence figure dans la section « Sources » (ou « Bibliographie », « Références »)
devient une note : la première fois la référence complète, ensuite « Voir note X. ». Les marqueurs [HYP] et [EST]
sont retirés. Titres, paragraphes, listes, tableaux, gras, italique et liens sont conservés.
Usage : python3 word.py LIVRABLE.md SORTIE.docx
"""
import io, re, sys, zipfile
from xml.sax.saxutils import escape

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
CITE = re.compile(r"\[(\d+(?:\s*[,;–-]\s*\d+)*)\]")
CITE_SPACE = re.compile(r"\s+(\[(\d+(?:\s*[,;–-]\s*\d+)*)\])")
SOURCES = re.compile(r"^#{1,4}\s*(sources|bibliographie|r[ée]f[ée]rences)\b", re.I)
REF_LINE = re.compile(r"^\s*(?:[-*]\s*)?(?:\[(\d+)\]|(\d+)[.)])\s+(.+)")


def numbers(group):
    out = []
    for part in re.split(r"\s*[,;]\s*", group):
        bounds = [int(x) for x in re.split(r"\s*[–-]\s*", part) if x]
        out += list(range(bounds[0], bounds[-1] + 1)) if len(bounds) == 2 and bounds[1] >= bounds[0] else bounds[:1]
    return out


def references(lines):
    refs, inside = {}, False
    for line in lines:
        if line.startswith("#"):
            inside = bool(SOURCES.match(line))
            continue
        m = REF_LINE.match(line) if inside else None
        if m:
            refs[int(m.group(1) or m.group(2))] = m.group(3).strip()
    return refs


class Doc:
    def __init__(self, refs):
        self.refs, self.notes, self.first = refs, [], {}

    def note(self, n):
        """Identifiant de la note pour la citation n : référence complète la première fois, puis renvoi."""
        nid = len(self.notes) + 1
        if n in self.first:
            text = f"Voir note {self.first[n]}."
        else:
            self.first[n] = nid
            text = clean(self.refs[n])
        self.notes.append(text)
        return nid

    def runs(self, text, cite=True):
        """Texte Markdown d'une ligne → runs Word (gras, italique, code, liens, notes)."""
        text = re.sub(r"\s*\[(HYP|EST)\]", "", text)
        if cite:  # la note se colle au mot qui précède, comme dans Word
            text = CITE_SPACE.sub(lambda m: m.group(1) if all(n in self.refs for n in numbers(m.group(2))) else m.group(0), text)
        text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", text)
        out = []
        for part in re.split(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[\d+(?:\s*[,;–-]\s*\d+)*\])", text):
            if not part:
                continue
            m = CITE.fullmatch(part)
            if cite and m and all(n in self.refs for n in numbers(m.group(1))):
                out += [f'<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="{self.note(n)}"/></w:r>' for n in numbers(m.group(1))]
            elif part.startswith("**"):
                out.append(run(part[2:-2], "<w:b/>"))
            elif part.startswith("`"):
                out.append(run(part[1:-1], '<w:rFonts w:ascii="Menlo" w:hAnsi="Menlo"/>'))
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                out.append(run(part[1:-1], "<w:i/>"))
            else:
                out.append(run(part))
        return "".join(out)


def run(text, props=""):
    return f'<w:r>{f"<w:rPr>{props}</w:rPr>" if props else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def clean(text):
    return re.sub(r"\*\*|__|(?<!\w)\*|\*(?!\w)|`", "", text)


def para(content, style=None, indent=0):
    ppr = (f'<w:pStyle w:val="{style}"/>' if style else "") + (f'<w:ind w:left="{indent}" w:hanging="280"/>' if indent else "")
    return f'<w:p>{f"<w:pPr>{ppr}</w:pPr>" if ppr else ""}{content}</w:p>'


def body(md, doc):
    xml, lines, i = [], md.replace("\r", "").split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or re.fullmatch(r"\s*([-*_])\s*\1\s*\1[\s\1]*", line):
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                xml.append(para(run(lines[i], '<w:rFonts w:ascii="Menlo" w:hAnsi="Menlo"/><w:sz w:val="18"/>')))
                i += 1
            i += 1
            continue
        m = re.match(r"(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            xml.append(para(doc.runs(m.group(2), cite=False), "Title" if level == 1 and not xml else f"Heading{min(level, 3)}"))
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|", lines[i + 1]):
            rows = [line]
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            xml.append('<w:tbl><w:tblPr><w:tblStyle w:val="Grille"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>' + "".join(
                "<w:tr>" + "".join(f'<w:tc><w:p>{doc.runs(f"**{c}**" if r == 0 and c else c)}</w:p></w:tc>' for c in row) + "</w:tr>"
                for r, row in enumerate(cells)) + "</w:tbl>")
            xml.append(para(""))
            continue
        m = re.match(r"\s*([-*+]|\d+[.)])\s+(.*)", line)
        if m:
            mark = "•" if m.group(1) in "-*+" else m.group(1)
            xml.append(para(run(mark + "\t") + doc.runs(m.group(2)), "Liste", 360))
            i += 1
            continue
        if line.startswith(">"):
            xml.append(para(doc.runs(line.lstrip("> ")), "Citation"))
            i += 1
            continue
        block = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"(#{1,4}\s|```|>|\s*([-*+]|\d+[.)])\s|\s*\|)", lines[i]):
            block.append(lines[i].strip())
            i += 1
        xml.append(para(doc.runs(" ".join(block))))
    return "".join(xml)


STYLES = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {W}>
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="22"/><w:lang w:val="fr-FR"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="160" w:after="60"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:sz w:val="23"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Liste"><w:name w:val="Liste"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="60"/><w:tabs><w:tab w:val="left" w:pos="360"/></w:tabs></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Citation"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="567"/></w:pPr><w:rPr><w:i/><w:color w:val="555555"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="FootnoteText"><w:name w:val="footnote text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="Grille"><w:name w:val="Grille"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="999999"/><w:left w:val="single" w:sz="4" w:color="999999"/><w:bottom w:val="single" w:sz="4" w:color="999999"/><w:right w:val="single" w:sz="4" w:color="999999"/><w:insideH w:val="single" w:sz="4" w:color="999999"/><w:insideV w:val="single" w:sz="4" w:color="999999"/></w:tblBorders><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
</w:styles>'''


def docx(md):
    """Markdown → octets du fichier .docx."""
    lines = md.replace("\r", "").split("\n")
    doc = Doc(references(lines))
    content = body(md, doc)
    notes = "".join(f'<w:footnote w:id="{i}"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr><w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>{run(" " + t)}</w:p></w:footnote>'
                    for i, t in enumerate(doc.notes, 1))
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/_rels/document.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/></Relationships>',
        "word/styles.xml": STYLES,
        "word/footnotes.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:footnotes {W}>'
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>' + notes + "</w:footnotes>",
        "word/document.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>{content}'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


if __name__ == "__main__":
    open(sys.argv[2], "wb").write(docx(open(sys.argv[1], encoding="utf-8").read()))
    print(f"Document Word écrit : {sys.argv[2]}")
