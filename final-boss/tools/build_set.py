#!/usr/bin/env python3
"""Generic Final Boss dataset builder.

Turns class-practice PDFs into a pluggable set:
  data/<id>.js + img/<id>/{sin,con}/<code>.jpg

It never invents diagnoses or structure names. It only copies text and
positions found in the PDF. Pages that do not look like a placa are skipped
and listed in the build report.

Usage:
  python3 tools/build_set.py --config tools/set.example.json
  python3 tools/build_set.py --config mi-parcial.json --dry-run

Primer parcial (clases 2–6) has official unlabeled JPGs and a verified JSON
of labels; use the specialized recipe instead:
  python3 build_data.py

See README_dataset.md for the schema, how silenciada images are made, and
how a new set appears in the menu.
"""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path

try:
    import pymupdf as fitz
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    sys.exit("Need pymupdf and Pillow: pip install pymupdf pillow")


CODE_RE = re.compile(r"\b(\d\d[-–]\d\d|\d+-\d+)\b")
SECCION_RE = re.compile(r"\s*[-–—]?\s*SECCI[OÓ]N\s+\d+\b", re.I)


def parse_pages(spec, page_count: int):
    if spec in (None, "", "all"):
        return list(range(1, page_count + 1))
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [p for p in out if 1 <= p <= page_count]


def strip_seccion(s: str) -> str:
    s = SECCION_RE.sub("", s or "")
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def compress(im: Image.Image, dest: Path, max_w=2400, quality=85):
    im = im.convert("RGB")
    w, h = im.size
    if w > max_w:
        nh = int(round(h * max_w / w))
        im = im.resize((max_w, nh), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)
    return im.size


def render_page(page, scale: float) -> Image.Image:
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def text_blocks(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for line in b.get("lines") or []:
            t = "".join(s.get("text", "") for s in line.get("spans") or [])
            t = re.sub(r"\s+", " ", t).strip()
            if not t:
                continue
            x0, y0, x1, y1 = line["bbox"]
            out.append({"text": t, "bbox": [x0, y0, x1, y1], "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return out


def find_code(blocks, page_w):
    for b in blocks:
        m = CODE_RE.search(b["text"])
        if m and (b["y0"] < 80 or b["x0"] > page_w * 0.7 or re.fullmatch(r"\d\d[-–]\d\d", b["text"])):
            return re.sub(r"–", "-", m.group(1)), b
    # last resort: any code-like token
    for b in blocks:
        m = re.fullmatch(r"\d\d[-–]\d\d", b["text"])
        if m:
            return re.sub(r"–", "-", m.group(0)), b
    return None, None


def find_diagnosis(blocks, code_box=None):
    # Prefer a long uppercase/title line near the top, not the code itself.
    cands = []
    for b in blocks:
        t = b["text"]
        if len(t) < 12:
            continue
        if CODE_RE.fullmatch(t):
            continue
        if re.match(r"^(clase|dr\.|universidad|ucsg)\b", t, re.I):
            continue
        score = 0
        if b["y0"] < 120:
            score += 3
        if t.isupper() or t[:8].isupper():
            score += 2
        if re.search(r"EMBRI|CORTE|VISTA|ETAPA|SECCI", t, re.I):
            score += 3
        if len(t) > 24:
            score += 1
        cands.append((score, -b["y0"], t))
    cands.sort(reverse=True)
    if not cands or cands[0][0] < 3:
        return None
    return strip_seccion(cands[0][2])


def is_structure_label(t: str) -> bool:
    if not t or len(t) > 80:
        return False
    if CODE_RE.fullmatch(t):
        return False
    if re.fullmatch(r"\d{1,3}", t):
        return False  # bare number badges stay visible
    if re.match(r"^(clase|dr\.|universidad|ucsg|final boss)\b", t, re.I):
        return False
    if len(t) < 3:
        return False
    return True


def structures_from_blocks(blocks, page_w, page_h, diagnosis):
    els = []
    n = 0
    for b in blocks:
        t = b["text"].strip()
        if not is_structure_label(t):
            continue
        if diagnosis and t == diagnosis:
            continue
        # skip huge title-like banners
        if b["y0"] < 40 and (b["x1"] - b["x0"]) > page_w * 0.5:
            continue
        n += 1
        x = 100.0 * (b["x0"] + b["x1"]) / 2.0 / page_w
        y = 100.0 * (b["y0"] + b["y1"]) / 2.0 / page_h
        w = 100.0 * (b["x1"] - b["x0"]) / page_w
        h = 100.0 * (b["y1"] - b["y0"]) / page_h
        poly = [
            [round(100.0 * b["x0"] / page_w, 3), round(100.0 * b["y0"] / page_h, 3)],
            [round(100.0 * b["x1"] / page_w, 3), round(100.0 * b["y0"] / page_h, 3)],
            [round(100.0 * b["x1"] / page_w, 3), round(100.0 * b["y1"] / page_h, 3)],
            [round(100.0 * b["x0"] / page_w, 3), round(100.0 * b["y1"] / page_h, 3)],
        ]
        els.append({
            "id": str(n),
            "name": t,
            "poly": poly,
            "n": n,
            "label": t,
            "x": round(x, 3),
            "y": round(y, 3),
            "w": round(max(w, 2), 3),
            "h": round(max(h, 2), 3),
        })
    return els


def mask_labels(im: Image.Image, blocks, scale, diagnosis) -> Image.Image:
    """Paint over structure name text; leave number badges and arrows."""
    out = im.copy()
    draw = ImageDraw.Draw(out)
    # sample a quiet background from a corner
    px = out.getpixel((min(8, out.width - 1), min(8, out.height - 1)))
    for b in blocks:
        t = b["text"].strip()
        if re.fullmatch(r"\d{1,3}", t):
            continue  # keep numbered markers
        if not is_structure_label(t) and t != diagnosis:
            continue
        x0, y0, x1, y1 = [v * scale for v in b["bbox"]]
        pad = 2 * scale
        box = [x0 - pad, y0 - pad, x1 + pad, y1 + pad]
        # try to sample local background just above the box
        sx = max(0, int(x0) - 4)
        sy = max(0, int(y0) - 8)
        try:
            fill = out.getpixel((min(sx, out.width - 1), min(sy, out.height - 1)))
        except Exception:
            fill = px
        draw.rectangle(box, fill=fill)
    return out


def write_dataset(cfg, placas, root: Path, report_lines):
    classes = {}
    for p in placas:
        c = str(p["cls"])
        classes[c] = classes.get(c, 0) + 1
    class_meta = {}
    for cinfo in cfg.get("classes") or []:
        cid = str(cinfo["id"])
        class_meta[cid] = {
            "name": cinfo.get("name") or f"Clase {cid}",
            "short": cinfo.get("short") or "",
            "count": classes.get(cid, 0),
        }
    for cid, n in classes.items():
        class_meta.setdefault(cid, {"name": f"Clase {cid}", "short": "", "count": n})

    set_id = cfg["id"]
    set_name = cfg.get("name") or set_id
    meta = {
        "title": "FINAL BOSS",
        "course": cfg.get("course") or set_name,
        "uni": cfg.get("uni") or "",
        "prof": cfg.get("prof") or "",
        "exam": cfg.get("exam") or "Diagnóstico completo + estructuras. Placas silenciadas.",
        "classes": class_meta,
        "total": len(placas),
        "passScore": int(cfg.get("passScore") or 80),
        "gaps": cfg.get("gaps") or [],
        "footer": cfg.get("footer") or "",
    }
    fb_set = {
        "id": set_id,
        "name": set_name,
        "course": meta["course"],
        "file": cfg.get("out_js") or f"data/{set_id}.js",
    }
    # structs index (optional, used by Mapa de los secretos)
    bag = {}
    for p in placas:
        for e in p.get("elements") or []:
            k = (e.get("name") or "").strip().lower()
            if not k:
                continue
            info = bag.setdefault(k, {"name": e["name"], "placas": set()})
            info["placas"].add(p["code"])
    structs = []
    for k, info in bag.items():
        cnt = len(info["placas"])
        color = "green" if cnt >= 6 else "gold" if cnt >= 3 else "red"
        structs.append({"key": k, "name": info["name"], "count": cnt, "placas": sorted(info["placas"]), "color": color})
    structs.sort(key=lambda s: (-s["count"], s["name"].lower()))
    cover = {"all": {"label": "Todo el parcial", "totalPlacas": len(placas), "totalStructs": len(structs), "route": [], "uniques": []}}

    js = (
        "/* Autogenerado desde materiales de clase. No inventar ni editar a mano. */\n"
        "window.FB_SET = " + json.dumps(fb_set, ensure_ascii=False, indent=2) + ";\n"
        "window.FB_META = " + json.dumps(meta, ensure_ascii=False, indent=2) + ";\n"
        "window.FB_PLACAS = " + json.dumps(placas, ensure_ascii=False) + ";\n"
        "window.FB_STRUCTS = " + json.dumps(structs, ensure_ascii=False) + ";\n"
        "window.FB_COVER = " + json.dumps(cover, ensure_ascii=False) + ";\n"
    )
    out = root / (cfg.get("out_js") or f"data/{set_id}.js")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(js, encoding="utf-8")
    report_lines.append(f"Wrote {out} ({len(js)//1024} KB), {len(placas)} placas")
    return out


def build(cfg, root: Path, dry=False):
    scale = float(cfg.get("dpi_scale") or 2.8)
    max_w = int(cfg.get("max_width") or 2400)
    quality = int(cfg.get("jpeg_quality") or 85)
    set_id = cfg["id"]
    img_dir = root / (cfg.get("img_dir") or f"img/{set_id}")
    sin_dir, con_dir = img_dir / "sin", img_dir / "con"
    report = [f"SET {set_id}  scale={scale} max_w={max_w}"]
    placas = []
    skipped = []
    for cinfo in cfg.get("classes") or []:
        pdf_path = Path(cinfo["pdf"])
        if not pdf_path.is_absolute():
            pdf_path = (root / pdf_path).resolve()
        if not pdf_path.exists():
            raise SystemExit(f"PDF not found: {pdf_path}")
        doc = fitz.open(str(pdf_path))
        pages = parse_pages(cinfo.get("pages"), doc.page_count)
        report.append(f"\n== Clase {cinfo.get('id')}  {pdf_path.name}  pages {pages} ==")
        for pno in pages:
            page = doc[pno - 1]
            blocks = text_blocks(page)
            pw, ph = page.rect.width, page.rect.height
            code, _ = find_code(blocks, pw)
            dx = find_diagnosis(blocks)
            if not code or not dx:
                skipped.append({"class": cinfo.get("id"), "page": pno, "reason": "no code or diagnosis", "code": code, "dx": dx})
                report.append(f"  SKIP p{pno}: no code/diagnosis (code={code!r} dx={dx!r})")
                continue
            els = structures_from_blocks(blocks, pw, ph, dx)
            if dry:
                report.append(f"  DRY {code} p{pno} els={len(els)}  {dx}")
                continue
            im = render_page(page, scale)
            rel_sin = f"{img_dir.name}/sin/{code}.jpg" if img_dir.name != "img" else f"sin/{code}.jpg"
            # keep paths as img/<set>/sin/code.jpg
            rel_sin = str((Path(cfg.get("img_dir") or f"img/{set_id}") / "sin" / f"{code}.jpg").as_posix())
            rel_con = str((Path(cfg.get("img_dir") or f"img/{set_id}") / "con" / f"{code}.jpg").as_posix())
            compress(im, root / rel_con, max_w=max_w, quality=quality)
            masked = mask_labels(im, blocks, scale, dx)
            compress(masked, root / rel_sin, max_w=max_w, quality=quality)
            placas.append({
                "code": code,
                "cls": str(cinfo["id"]),
                "class": str(cinfo["id"]),
                "deck": cinfo.get("name") or f"Clase {cinfo['id']}",
                "pdf": pdf_path.name,
                "page": pno,
                "diagnosis": dx,
                "diagnosis_slide": dx,
                "parts": [],
                "numbered": True,
                "elements": [{"id": e["id"], "name": e["name"], "poly": e["poly"]} for e in els],
                "structures": [{"n": e["n"], "label": e["label"], "x": e["x"], "y": e["y"]} for e in els],
                "structureOK": len(els) >= 4,
                "same": [],
                "imgSin": rel_sin,
                "imgCon": rel_con,
                "img_silenciada": rel_sin,
                "img_con_nombres": rel_con,
            })
            report.append(f"  {code} p{pno} nEl={len(els):2}  {dx}")
        doc.close()
    if not dry:
        if not placas:
            raise SystemExit("No placas extracted. Refusing to write an empty set (no fake data).")
        write_dataset(cfg, placas, root, report)
    report.append(f"\nSKIPPED {len(skipped)}")
    for s in skipped:
        report.append(f"  {s}")
    report_path = root / f"build_report_{set_id}.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"\nReport: {report_path}")


def main():
    ap = argparse.ArgumentParser(description="Build a Final Boss placa set from class PDFs")
    ap.add_argument("--config", required=True, help="JSON config (see tools/set.example.json)")
    ap.add_argument("--root", default=".", help="Set root (folder with data/ and img/)")
    ap.add_argument("--dry-run", action="store_true", help="Parse PDFs and print what would be extracted; write no images")
    args = ap.parse_args()
    cfg_path = Path(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if not cfg.get("id") or not cfg.get("name"):
        sys.exit("config needs id and name")
    if not cfg.get("classes"):
        sys.exit("config needs classes[] with pdf + pages")
    root = Path(args.root).resolve()
    build(cfg, root, dry=args.dry_run)


if __name__ == "__main__":
    main()
