#!/usr/bin/env python3
"""Render a fixed, reproducible corpus of document images for the OCR study.

The pre-registration requires a corpus that is identical across every condition
and both prompt regimes, and that ships with the released data. Shipping the
images themselves would add megabytes of binaries to a repository that already
carries gigabytes of telemetry, and would leave the reader unable to check how
they were made. So the corpus is this script plus the text it renders, and the
text comes from files already in the repository: real English prose, no licence
question, and byte-identical on any machine that runs this.

Determinism matters more than realism here. Page size, font, point size, margins
and the character offsets into each source file are all fixed, so two runs
produce the same images and two conditions see the same prefill cost.

Usage:
    python3 scripts/make_ocr_corpus.py [full|compact] [out_dir]
"""
import os
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

# Page geometry. The first pilot rendered A4 at roughly 125 dpi, 1024x1448, and
# that was a mistake worth recording: the vision encoder turned such a page into
# about 7,330 prompt tokens regardless of what was asked of it, which fixed the
# workload in the prefill-dominated regime and made the decode-dominated arm
# unreachable by prompting. It also cost about 270 s per inference, with the
# denser pages timing out entirely.
#
# Halving the linear dimensions quarters the patch count and so the prefill
# cost. Point size is deliberately NOT reduced with it: legibility for OCR
# depends on pixels per character, not on the nominal page size, so the smaller
# page carries less text at the same readability rather than the same text
# smaller.
PROFILES = {
    "full":    dict(w=1024, h=1448, margin=72, pt=19),
    "compact": dict(w=512,  h=724,  margin=40, pt=19),
}
LINE_SPACING = 1.45

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# (source file, character offset, page label). Offsets are fixed so the corpus
# does not drift when these files are edited near their ends; if an edit lands
# before an offset the corpus changes, which is why the generator is versioned
# alongside the data it produces.
PAGES = [
    ("logs/MANIFEST.md", 0, "manifest-1"),
    ("logs/MANIFEST.md", 1800, "manifest-2"),
    ("docs/RUNBOOK.md", 0, "runbook-1"),
    ("docs/RUNBOOK.md", 2400, "runbook-2"),
    ("README.md", 400, "readme-1"),
    ("logs/LICENSE", 0, "licence-1"),
]


def load_font(pt):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, pt), p
    raise SystemExit("no usable serif font found; install fonts-dejavu")


def clean(s):
    """Strip markdown furniture, so the page reads as prose rather than source."""
    out = []
    for line in s.split("\n"):
        t = line.strip()
        if t.startswith("|") or t.startswith("```") or set(t) <= {"-", " ", "="}:
            continue
        for ch in ("#", "*", "`", "_", ">"):
            t = t.replace(ch, "")
        if t:
            out.append(t)
    return " ".join(out)


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    profile = sys.argv[1] if len(sys.argv) > 1 else "compact"
    if profile not in PROFILES:
        raise SystemExit(f"profile must be one of {list(PROFILES)}")
    g = PROFILES[profile]
    PAGE_W, PAGE_H, MARGIN, PT = g["w"], g["h"], g["margin"], g["pt"]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(repo, "logs", f"ocr_corpus_{profile}")
    os.makedirs(out_dir, exist_ok=True)
    print(f"  profile {profile}: {PAGE_W}x{PAGE_H}, {PT}pt")

    font, font_path = load_font(PT)
    line_h = int(PT * LINE_SPACING)
    usable_w = PAGE_W - 2 * MARGIN
    max_lines = (PAGE_H - 2 * MARGIN) // line_h

    # Characters per line, measured rather than guessed, so the wrap is stable
    # across fonts that happen to be installed.
    probe = "n" * 200
    while font.getlength(probe) > usable_w and len(probe) > 10:
        probe = probe[:-1]
    cpl = len(probe)

    manifest = []
    for src, offset, label in PAGES:
        path = os.path.join(repo, src)
        if not os.path.exists(path):
            print(f"  skip {label}: {src} not found")
            continue
        text = clean(open(path, errors="ignore").read()[offset:])
        lines = textwrap.wrap(text, width=cpl)[:max_lines]
        if not lines:
            print(f"  skip {label}: no text at offset {offset}")
            continue

        img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        d = ImageDraw.Draw(img)
        y = MARGIN
        for ln in lines:
            d.text((MARGIN, y), ln, font=font, fill="black")
            y += line_h

        name = f"{label}.png"
        img.save(os.path.join(out_dir, name))
        words = sum(len(l.split()) for l in lines)
        manifest.append((name, src, offset, len(lines), words))
        print(f"  {name:<16} {len(lines):>3} lines  {words:>4} words  from {src}@{offset}")

    with open(os.path.join(out_dir, "CORPUS.md"), "w") as f:
        f.write("# OCR corpus\n\n")
        f.write("Generated by `scripts/make_ocr_corpus.py`. Do not edit these images by\n")
        f.write("hand: regenerate them, so that what produced them stays checkable.\n\n")
        f.write(f"Page {PAGE_W}x{PAGE_H}, {PT}pt, font `{font_path}`, {cpl} characters per line.\n\n")
        f.write("| image | source | offset | lines | words |\n|---|---|---|---|---|\n")
        for n, s, o, l, w in manifest:
            f.write(f"| `{n}` | `{s}` | {o} | {l} | {w} |\n")
    print(f"\n  {len(manifest)} pages written to {out_dir}")


if __name__ == "__main__":
    main()
