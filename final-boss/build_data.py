#!/usr/bin/env python3
"""Rebuild Final Boss data + unlabeled/labeled images for clases 2-6."""
from __future__ import annotations
import json, re, unicodedata
from collections import defaultdict
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/workspace/morfo/final_boss")
SIN = ROOT / "img" / "sin"
CON = ROOT / "img" / "con"
SIN.mkdir(parents=True, exist_ok=True)
CON.mkdir(parents=True, exist_ok=True)

UCSG = Path("/workspace/ucsg/MORFO_GENESIS_III_A1P")
UCSG_JSON = UCSG / "leccion_practica_2-4/work/placas_2-4.json"
IMG_SIN_24 = UCSG / "leccion_practica_2-4/img_sin"
IMG_CON_SRC = Path("/workspace/morfo/placas_app_c2_c3_c4/img")  # original labeled diapos
IMG_C5_LAB = Path("/workspace/morfo/placas_app_c2_c3/img")
C5_JSON = Path("/workspace/morfo/placas_app_c2_c3/placas_c2_c3.json")
PDF5 = UCSG / "CLASE 05 - ORIGEN DEL SISTEMA NERVIOSO AUTONOMO.pdf"
PDF6 = UCSG / "CLASE 06 - PROCENCEFALO, TELENCEFALO Y DIENCEFALO.pdf"

DECKS = {
    "2": "Clase 2 — Gastrulación y neurulación",
    "3": "Clase 3 — Tubo neural y médula espinal",
    "4": "Clase 4 — Cresta neural",
    "5": "Clase 5 — Sistema nervioso autónomo",
    "6": "Clase 6 — Prosencéfalo (telencéfalo y diencéfalo)",
}

SECCION_RE = re.compile(r"\s*[-–—]?\s*SECCI[OÓ]N\s+\d+\b", re.I)
POLLO = re.compile(
    r"^(EMBRIÓN DE POLLO)\s+"
    r"(DE\s+(?:\d+\s+SOMITAS(?:\s+\([^)]+\))?|\d+\s+SEGMENTOS|\d+\s+D[IÍ]AS(?:\s+\([^)]+\))?|\d+\s+HORAS))"
    r"\s*[-–]?\s*"
    r"(CORTE\s+.+|VISTA\s+.+)?$"
)
CARN = re.compile(
    r"^(EMBRI[OÓ]N)\s+ETAPA CARNEGIE\s+(.+?D[IÍ]AS)(?:\s+(\(.+\)))?$"
)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def strip_seccion(s: str) -> str:
    s = SECCION_RE.sub("", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+\)", ")", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+-\s+\(", " (", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def parse_parts(dx: str):
    m = CARN.match(dx)
    if m:
        parts = [
            {"key": "tipo", "prompt": "¿Qué tipo de embrión es?", "value": f"{m.group(1)} ETAPA CARNEGIE"},
            {"key": "etapa", "prompt": "¿Cuál es la etapa?", "value": m.group(2).strip()},
        ]
        if m.group(3):
            parts.append({"key": "region", "prompt": "¿Cuál es la región?", "value": m.group(3).strip()})
        return parts
    m = POLLO.match(dx)
    if m:
        parts = [
            {"key": "tipo", "prompt": "¿Qué tipo de embrión es?", "value": m.group(1)},
            {"key": "etapa", "prompt": "¿Cuál es la etapa o el tiempo?", "value": m.group(2).strip()},
        ]
        if m.group(3):
            parts.append({"key": "corte", "prompt": "¿Cuál es el corte o la vista?", "value": m.group(3).strip()})
        return parts
    raise ValueError(f"Cannot parse diagnosis: {dx}")


def norm_name(s: str) -> str:
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[.,;:()\[\]¿?¡!]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compress(src: Image.Image | Path, dest: Path, max_w=2400, quality=85):
    if isinstance(src, Path) or isinstance(src, str):
        im = Image.open(src).convert("RGB")
    else:
        im = src.convert("RGB")
    w, h = im.size
    if w > max_w:
        nh = int(round(h * max_w / w))
        im = im.resize((max_w, nh), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)
    return im.size


def poly_ok(poly) -> bool:
    if not poly or len(poly) < 4:
        return False
    for x, y in poly:
        if not (-2 <= x <= 102 and -2 <= y <= 102):
            return False
    return True


def extract_c56(pdf_path: Path, pages, cls: str, deck: str, existing_els=None):
    """Extract labeled + unlabeled (text-redacted + number badges) for clases 5-6.

    existing_els: optional dict code -> elements (to keep previously extracted names/polys).
    We re-extract for consistent crop + clean sin images. If existing_els provided,
    we prefer those names (already verified) but recompute images with same method.
    """
    d = fitz.open(str(pdf_path))
    S = 2.8
    out = []
    for pno in pages:
        src_page = d[pno - 1]
        W, H = src_page.rect.width, src_page.rect.height
        lines, title, code, ty = [], [], None, 0
        for b in src_page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for l in b["lines"]:
                t = re.sub(r"\s+", " ", "".join(s["text"] for s in l["spans"])).strip()
                bb = fitz.Rect(l["bbox"])
                if not t:
                    continue
                if re.fullmatch(r"\d\d-\d\d", t):
                    code = t
                    continue
                if t == "1" and bb.x1 < 50:
                    continue
                if bb.y0 < 16 and re.match(r"EMBRI", t, re.I):
                    title.append(t)
                    ty = max(ty, bb.y1)
                    continue
                lines.append((t, bb))
        lines.sort(key=lambda x: (x[1].y0, x[1].x0))
        groups = []
        for t, bb in lines:
            merged = False
            if groups:
                prev_t, prev_bb = groups[-1]
                close_y = 0 <= bb.y0 - prev_bb.y1 < 8 or (bb.y0 - prev_bb.y0 < 28 and bb.y0 > prev_bb.y0)
                same_x = abs(bb.x0 - prev_bb.x0) < 8
                # Only wrap obvious line-breaks of one label (e.g. "anterior y post"),
                # never two complete structure names that happen to be stacked.
                frag = re.match(r'^(anterior|posterior|y |de la |de las |del |de los )', t, re.I)
                cont = bool(frag) or (len(t) <= 16 and t[:1].islower() and not re.match(
                    r'^(nervio|ganglio|arteria|vena|m[uú]sculo|hueso|placa|surco|n[uú]cleo)', t, re.I))
                if close_y and same_x and cont:
                    groups[-1] = (prev_t + " " + t, prev_bb | bb)
                    merged = True
            if not merged:
                groups.append((t, fitz.Rect(bb)))
        top = ty + 2
        clip = fitz.Rect(0, top, W, H)

        # Labeled render
        pix = src_page.get_pixmap(matrix=fitz.Matrix(S, S), clip=clip)
        lab = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        iw, ih = lab.size

        els = []
        for name, r in groups:
            name = name.strip()
            if not name:
                continue
            rr = r + (-3, -1, 3, 1)
            poly = [
                [round(x * S / iw * 100, 3), round((y - top) * S / ih * 100, 3)]
                for x, y in [(rr.x0, rr.y0), (rr.x1, rr.y0), (rr.x1, rr.y1), (rr.x0, rr.y1)]
            ]
            els.append({"name": name, "poly": poly, "_y": r.y0, "_x": r.x0, "_r": r})
        els.sort(key=lambda e: (round(e["_y"] / 12), e["_x"]))
        for i, e in enumerate(els, 1):
            e["id"] = str(i)
            e.pop("_y"); e.pop("_x")

        # Unlabeled: redact all text, render same clip, stamp compact badges
        doc2 = fitz.open(str(pdf_path))
        page2 = doc2[pno - 1]
        for b in page2.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for l in b["lines"]:
                r = fitz.Rect(l["bbox"]) + (-1, -1, 1, 1)
                page2.add_redact_annot(r, fill=(1, 1, 1))
        try:
            page2.apply_redactions(images=0)
        except TypeError:
            page2.apply_redactions()
        pixs = page2.get_pixmap(matrix=fitz.Matrix(S, S), clip=clip)
        silent = Image.frombytes("RGB", (pixs.width, pixs.height), pixs.samples)
        doc2.close()
        # safety: if any residual dark text in label boxes, cover them
        draw = ImageDraw.Draw(silent)
        try:
            font = ImageFont.truetype(FONT, max(16, int(iw / 70)))
        except Exception:
            font = ImageFont.load_default()
        for e in els:
            r = e.pop("_r")
            # badge at label centroid, compact
            cx = (e["poly"][0][0] + e["poly"][2][0]) / 2 * iw / 100
            cy = (e["poly"][0][1] + e["poly"][2][1]) / 2 * ih / 100
            # also paint over the original (possibly residual) text box
            xs = [pt[0] * iw / 100 for pt in e["poly"]]
            ys = [pt[1] * ih / 100 for pt in e["poly"]]
            pad = 3
            # white out any leftover glyphs in the text area
            draw.rounded_rectangle(
                [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad],
                radius=6,
                fill=(255, 255, 255),
            )
            # compact id badge
            lab_id = e["id"]
            tb = draw.textbbox((0, 0), lab_id, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            bw, bh = max(26, tw + 14), max(22, th + 10)
            box = [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]
            draw.rounded_rectangle(box, radius=8, fill=(255, 248, 230), outline=(30, 30, 30), width=2)
            draw.text((cx - tw / 2, cy - th / 2 - tb[1]), lab_id, fill=(20, 20, 20), font=font)

        out.append({
            "code": code,
            "cls": cls,
            "deck": deck,
            "pdf": pdf_path.name,
            "page": pno,
            "diagnosis_slide": " ".join(title).strip(),
            "w": iw,
            "h": ih,
            "numbered": True,  # we stamp 1..n
            "elements": els,
            "lab_im": lab,
            "sin_im": silent,
        })
    d.close()
    return out


def elements_from_ucsg(els):
    out = []
    for e in els:
        item = {
            "id": str(e.get("id") or e.get("num") or ""),
            "name": e["name"],
            "poly": e.get("poly") or [],
        }
        if e.get("canon") and e["canon"] != e["name"]:
            item["canon"] = e["canon"]
        item["key"] = norm_name(e.get("canon") or e["name"])
        out.append(item)
    return out


def greedy_cover(codes, key_to_codes):
    uncovered = set(codes)
    picked = []
    used = set()
    while uncovered:
        best, best_hit = None, set()
        for k, pcs in key_to_codes.items():
            if k in used:
                continue
            hit = set(pcs) & uncovered
            if len(hit) > len(best_hit) or (len(hit) == len(best_hit) and best and k < best):
                if hit:
                    best, best_hit = k, hit
        if not best:
            break
        used.add(best)
        picked.append({"key": best, "covers": len(best_hit), "codes": sorted(best_hit)})
        uncovered -= best_hit
    return picked, sorted(uncovered)


def main():
    placas = []

    # ----- Clases 2-4: official silenciadas + original labeled diapos -----
    ucsg = json.loads(UCSG_JSON.read_text())
    for p in ucsg:
        code = p["code"]
        cls = str(p.get("cls") or code.split("-")[0].lstrip("0"))
        src_sin = IMG_SIN_24 / f"{code}.jpg"
        src_con = IMG_CON_SRC / f"{code}.jpg"
        if not src_sin.exists():
            raise SystemExit(f"Missing silenciada {src_sin}")
        if not src_con.exists():
            raise SystemExit(f"Missing labeled {src_con}")
        compress(src_sin, SIN / f"{code}.jpg")
        compress(src_con, CON / f"{code}.jpg")
        diag_slide = (p.get("diagnosis_full") or p.get("diagnosis") or "").strip()
        dx = strip_seccion(diag_slide)
        els = elements_from_ucsg(p.get("elements") or [])
        ok = sum(1 for e in els if poly_ok(e["poly"]))
        placas.append({
            "code": code,
            "cls": cls,
            "deck": DECKS[cls],
            "pdf": p.get("pdf") or "",
            "page": p.get("page"),
            "diagnosis_slide": diag_slide,
            "diagnosis": dx,
            "parts": parse_parts(dx),
            "numbered": bool(p.get("numbered")),
            "elements": els,
            "structureOK": ok >= 3 and ok / max(1, len(els)) >= 0.8,
            "same": [],
            "imgSin": f"img/sin/{code}.jpg",
            "imgCon": f"img/con/{code}.jpg",
        })

    # ----- Clase 5: pages 17-22 -----
    c5_existing = {p["code"]: p for p in json.loads(C5_JSON.read_text()) if p["code"].startswith("05-")}
    for pl in extract_c56(PDF5, range(17, 23), "5", DECKS["5"]):
        code = pl["code"]
        # Prefer already-verified names from prior extraction if counts match
        prev = c5_existing.get(code)
        if prev and len(prev.get("elements") or []) == len(pl["elements"]):
            for a, b in zip(pl["elements"], elements_from_c5_keep(prev["elements"])):
                if norm_name(a["name"]) != norm_name(b["name"]) and a["name"].rstrip(" .") != b["name"].rstrip(" ."):
                    # keep PDF text (source of truth) but log
                    print(f"  name diff {code}: {a['name']!r} vs {b['name']!r}")
        compress(pl["lab_im"], CON / f"{code}.jpg")
        compress(pl["sin_im"], SIN / f"{code}.jpg")
        dx = strip_seccion(pl["diagnosis_slide"])
        els = []
        for e in pl["elements"]:
            els.append({"id": e["id"], "name": e["name"].strip().rstrip(" ."), "poly": e["poly"], "key": norm_name(e["name"])})
        ok = sum(1 for e in els if poly_ok(e["poly"]))
        placas.append({
            "code": code, "cls": "5", "deck": DECKS["5"], "pdf": PDF5.name, "page": pl["page"],
            "diagnosis_slide": pl["diagnosis_slide"], "diagnosis": dx, "parts": parse_parts(dx),
            "numbered": True, "elements": els,
            "structureOK": ok >= 3 and ok / max(1, len(els)) >= 0.8,
            "same": [], "imgSin": f"img/sin/{code}.jpg", "imgCon": f"img/con/{code}.jpg",
        })

    # ----- Clase 6: pages 2-7 -----
    for pl in extract_c56(PDF6, range(2, 8), "6", DECKS["6"]):
        code = pl["code"]
        compress(pl["lab_im"], CON / f"{code}.jpg")
        compress(pl["sin_im"], SIN / f"{code}.jpg")
        dx = strip_seccion(pl["diagnosis_slide"])
        els = []
        for e in pl["elements"]:
            els.append({"id": e["id"], "name": e["name"].strip().rstrip(" ."), "poly": e["poly"], "key": norm_name(e["name"])})
        ok = sum(1 for e in els if poly_ok(e["poly"]))
        placas.append({
            "code": code, "cls": "6", "deck": DECKS["6"], "pdf": PDF6.name, "page": pl["page"],
            "diagnosis_slide": pl["diagnosis_slide"], "diagnosis": dx, "parts": parse_parts(dx),
            "numbered": True, "elements": els,
            "structureOK": ok >= 3 and ok / max(1, len(els)) >= 0.8,
            "same": [], "imgSin": f"img/sin/{code}.jpg", "imgCon": f"img/con/{code}.jpg",
        })

    placas.sort(key=lambda p: (int(p["cls"]), p["code"]))

    by_dx = defaultdict(list)
    for p in placas:
        by_dx[p["diagnosis"]].append(p["code"])
    for p in placas:
        p["same"] = [c for c in by_dx[p["diagnosis"]] if c != p["code"]]

    # Frequency + set cover
    key_info = {}  # key -> {name, canon, placas:set}
    for p in placas:
        seen = set()
        for e in p["elements"]:
            k = e.get("key") or norm_name(e["name"])
            if k in seen:
                continue
            seen.add(k)
            info = key_info.setdefault(k, {"forms": defaultdict(int), "placas": set(), "canon": None})
            form = e.get("canon") or e["name"]
            info["forms"][form] += 1
            if e.get("canon"):
                info["canon"] = e["canon"]
            info["placas"].add(p["code"])

    structs = []
    for k, info in key_info.items():
        name = info["canon"] or max(info["forms"].items(), key=lambda kv: kv[1])[0]
        cnt = len(info["placas"])
        if cnt >= 4:
            color = "green"
        elif cnt >= 2:
            color = "gold"
        else:
            color = "red"
        structs.append({
            "key": k, "name": name, "count": cnt,
            "placas": sorted(info["placas"]), "color": color,
        })
    structs.sort(key=lambda s: (-s["count"], s["name"].lower()))

    def cover_for(codes, label):
        sub = {s["key"]: [c for c in s["placas"] if c in codes] for s in structs}
        sub = {k: v for k, v in sub.items() if v}
        picked, leftover = greedy_cover(codes, sub)
        # fill display names
        k2n = {s["key"]: s["name"] for s in structs}
        for item in picked:
            item["name"] = k2n[item["key"]]
        uniques = [s for s in structs if s["color"] == "red" and any(c in codes for c in s["placas"])]
        return {
            "label": label,
            "totalPlacas": len(codes),
            "totalStructs": len(sub),
            "route": picked,
            "uniques": [{"key": s["key"], "name": s["name"], "codes": [c for c in s["placas"] if c in codes]} for s in uniques],
        }

    cover = {"all": cover_for([p["code"] for p in placas], "Todo el parcial")}
    for c in ["2", "3", "4", "5", "6"]:
        cover[c] = cover_for([p["code"] for p in placas if p["cls"] == c], DECKS[c])

    # Report
    lines = [f"TOTAL {len(placas)} placas"]
    for cls in ["2", "3", "4", "5", "6"]:
        subset = [p for p in placas if p["cls"] == cls]
        lines.append(f"\n== Clase {cls} ({len(subset)}) {DECKS[cls]} ==")
        for p in subset:
            n = len(p["elements"])
            sok = "OK" if p["structureOK"] else "NO-ST"
            sin_kb = (ROOT / p["imgSin"]).stat().st_size // 1024
            con_kb = (ROOT / p["imgCon"]).stat().st_size // 1024
            lines.append(f"  {p['code']} nEl={n:2} {sok} sin={sin_kb}KB con={con_kb}KB  {p['diagnosis']}")
            lines.append("       parts: " + " | ".join(x["value"] for x in p["parts"]))
    lines.append("\n== Diagnósticos compartidos ==")
    for dx, codes in by_dx.items():
        if len(codes) > 1:
            lines.append(f"  {codes}: {dx}")
    lines.append(f"\n== Estructuras únicas (norm) {len(structs)} ==")
    lines.append(f"  green={sum(1 for s in structs if s['color']=='green')} gold={sum(1 for s in structs if s['color']=='gold')} red={sum(1 for s in structs if s['color']=='red')}")
    report = "\n".join(lines) + "\n"
    (ROOT / "build_report.txt").write_text(report, encoding="utf-8")
    print(report)

    meta = {
        "title": "FINAL BOSS",
        "course": "Morfogénesis III · Práctica · Primer parcial",
        "uni": "UCSG · Escuela de Medicina",
        "prof": "Dr. Juan Pablo Herrera Valdivieso",
        "exam": "Diagnóstico completo palabra por palabra + 4 estructuras. El profe no pregunta números de sección. En el examen las placas van silenciadas (sin nombres).",
        "classes": {k: {"name": v, "count": sum(1 for p in placas if p["cls"] == k)} for k, v in DECKS.items()},
        "total": len(placas),
        "passScore": 80,
        "gaps": [
            "Clase 01 es presentación/reglas, no trae placas de práctica.",
            "Clase 07 es entrega de notas, no trae placas.",
            "No hay más clases de práctica en el primer parcial.",
            "Clases 5 y 6: las placas silenciadas se generaron tapando el texto de las diapos oficiales y dejando flechas + números; hay que confirmar visualmente que no quede texto.",
        ],
    }

    fb_set = {
        "id": "primer-parcial",
        "name": "Primer parcial",
        "course": meta["course"],
        "file": "data/primer-parcial.js",
    }
    data_js = (
        "/* Autogenerado desde materiales de clase. No inventar ni editar a mano. */\n"
        "window.FB_SET = " + json.dumps(fb_set, ensure_ascii=False, indent=2) + ";\n"
        "window.FB_META = " + json.dumps(meta, ensure_ascii=False, indent=2) + ";\n"
        "window.FB_PLACAS = " + json.dumps(placas, ensure_ascii=False) + ";\n"
        "window.FB_STRUCTS = " + json.dumps(structs, ensure_ascii=False) + ";\n"
        "window.FB_COVER = " + json.dumps(cover, ensure_ascii=False) + ";\n"
    )
    out = ROOT / "data" / "primer-parcial.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(data_js, encoding="utf-8")
    print(f"Wrote {out} ({len(data_js)//1024} KB)")
    print("sin total KB", sum(f.stat().st_size for f in SIN.glob('*.jpg')) // 1024)
    print("con total KB", sum(f.stat().st_size for f in CON.glob('*.jpg')) // 1024)


def elements_from_c5_keep(els):
    out = []
    for e in els:
        name = e["name"].strip()
        name = re.sub(r"\s+\.$", "", name)
        out.append({"name": name})
    return out


if __name__ == "__main__":
    main()
