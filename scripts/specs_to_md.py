"""Convert a DOCX spec into Markdown, preserving headings, lists, tables and line breaks."""

import sys
import xml.etree.ElementTree as ET
import zipfile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TEXT_TAGS = {f"{W}t", f"{W}br", f"{W}cr", f"{W}tab"}


def ptext(p):
    style = p.find(f"{W}pPr/{W}pStyle")
    s = style.get(f"{W}val") if style is not None else ""
    parts = []
    for x in p.iter():
        if x.tag not in TEXT_TAGS:
            continue
        if x.tag == f"{W}t":
            parts.append(x.text or "")
        elif x.tag == f"{W}tab":
            parts.append("\t")
        else:
            parts.append("\n")
    return s, "".join(parts)


def cell(t):
    return t.replace("|", "\\|").replace("\n", " ")


def walk(body, out):
    for el in body:
        if el.tag == f"{W}p":
            s, t = ptext(el)
            if not t.strip():
                continue
            low = s.lower()
            if t.count("\n") > 2:
                out.append("```text\n" + t + "\n```")
            elif low.startswith("heading"):
                lvl = int("".join(c for c in s if c.isdigit()) or 1)
                out.append("\n" + "#" * (lvl + 1) + " " + t)
            elif low == "title":
                out.append("# " + t)
            elif "list" in low or el.find(f"{W}pPr/{W}numPr") is not None:
                out.append("- " + t)
            else:
                out.append(t)
        elif el.tag == f"{W}tbl":
            out.append("")
            for i, tr in enumerate(el.findall(f"{W}tr")):
                cells = []
                for tc in tr.findall(f"{W}tc"):
                    texts = [ptext(p)[1] for p in tc.findall(f".//{W}p")]
                    cells.append(cell(" ".join(t for t in texts if t.strip())))
                out.append("| " + " | ".join(cells) + " |")
                if i == 0:
                    out.append("|" + "---|" * len(cells))
            out.append("")
        elif el.tag == f"{W}sdt":
            c = el.find(f"{W}sdtContent")
            if c is not None:
                walk(c, out)


def main(src, dst):
    z = zipfile.ZipFile(src)
    root = ET.fromstring(z.read("word/document.xml"))
    out = [
        f"<!-- Generated from {src.split('/')[-1]} (authoritative source). Do not edit by hand. -->"
    ]
    walk(root.find(f"{W}body"), out)
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print(dst, len(out), "blocks")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
