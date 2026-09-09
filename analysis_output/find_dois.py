#!/usr/bin/env python3
"""Look up DOIs for bibliography entries that lack one, and refuse to guess.

A wrong DOI resolves to somebody else's paper, which is worse than no DOI at
all: a reader following it is misled and a production editor will not catch it.
So every candidate is accepted only when the Crossref title matches the entry
title closely AND the years agree. Anything weaker is reported for a human to
check, never written.

Usage:  find_dois.py <references.bib>            # report only
        find_dois.py <references.bib> --apply    # write the confident ones
"""
import difflib
import json
import re
import sys
import time
import urllib.parse
import urllib.request

AUTO = 0.93   # accept without asking
MAYBE = 0.75  # report for a human below this only as "no match"


def entries(txt):
    out = []
    for m in re.finditer(r'@(\w+)\s*\{\s*([^,\s]+)\s*,', txt):
        i = txt.index('{', m.start())
        depth = 0
        for j in range(i, len(txt)):
            if txt[j] == '{':
                depth += 1
            elif txt[j] == '}':
                depth -= 1
                if depth == 0:
                    out.append((m.group(1), m.group(2), m.start(), j + 1))
                    break
    return out


def field(body, name):
    m = re.search(name + r'\s*=\s*[{"]', body, re.I)
    if not m:
        return ""
    i = m.end() - 1
    if body[i] == '"':
        j = body.index('"', i + 1)
        return body[i + 1:j]
    depth = 0
    for j in range(i, len(body)):
        if body[j] == '{':
            depth += 1
        elif body[j] == '}':
            depth -= 1
            if depth == 0:
                return body[i + 1:j]
    return ""


def norm(t):
    t = re.sub(r'\\[a-zA-Z]+', ' ', t)
    t = re.sub(r'[{}$\\]', '', t)
    t = re.sub(r'[^a-z0-9 ]', ' ', t.lower())
    return re.sub(r'\s+', ' ', t).strip()


def crossref(title):
    q = urllib.parse.urlencode({"query.bibliographic": title, "rows": 3})
    req = urllib.request.Request(
        "https://api.crossref.org/works?" + q,
        headers={"User-Agent": "bib-doi-check/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)["message"].get("items", [])


def year_of(item):
    for k in ("published-print", "published-online", "issued", "created"):
        p = item.get(k, {}).get("date-parts", [[None]])
        if p and p[0] and p[0][0]:
            return p[0][0]
    return None


def main():
    path = sys.argv[1]
    apply_ = "--apply" in sys.argv
    txt = open(path, encoding="utf-8").read()
    found, weak, none_ = [], [], []

    for etype, key, a, b in entries(txt):
        body = txt[a:b]
        if re.search(r'\bdoi\s*=', body, re.I):
            continue
        title = field(body, "title")
        if not title:
            none_.append((key, "no title field"))
            continue
        year = field(body, "year")
        try:
            items = crossref(norm(title))
        except Exception as exc:
            none_.append((key, f"query failed: {exc}"))
            continue
        time.sleep(1.1)   # public pool: stay polite
        best = None
        for it in items:
            ct = (it.get("title") or [""])[0]
            if not ct:
                continue
            ratio = difflib.SequenceMatcher(None, norm(title), norm(ct)).ratio()
            cy = year_of(it)
            ok_year = (not year or not cy or abs(int(year) - cy) <= 1)
            if best is None or ratio > best[0]:
                best = (ratio, it.get("DOI"), ct, cy, ok_year)
        if best is None:
            none_.append((key, "no candidates"))
        elif best[0] >= AUTO and best[4]:
            found.append((key, best[1], best[0], title, best[2]))
        elif best[0] >= MAYBE:
            weak.append((key, best[1], best[0], title, best[2], best[3], best[4]))
        else:
            none_.append((key, f"best ratio {best[0]:.2f}"))

    print(f"\n=== confident ({len(found)}) ===")
    for k, doi, r, _t, _ct in found:
        print(f"  {k:<26} {r:.2f}  {doi}")
    print(f"\n=== needs a human ({len(weak)}) ===")
    for k, doi, r, t, ct, cy, oky in weak:
        print(f"  {k:<26} {r:.2f} year_ok={oky}  {doi}")
        print(f"      bib: {t[:88]}")
        print(f"      xref: {ct[:88]} ({cy})")
    print(f"\n=== no match ({len(none_)}) ===")
    for k, why in none_:
        print(f"  {k:<26} {why}")

    if apply_ and found:
        for k, doi, _r, _t, _ct in found:
            m = re.search(r'(@\w+\s*\{\s*' + re.escape(k) + r'\s*,)', txt)
            txt = txt[:m.end()] + f"\n  doi       = {{{doi}}}," + txt[m.end():]
        open(path, "w", encoding="utf-8").write(txt)
        print(f"\nwrote {len(found)} DOIs into {path}")


if __name__ == "__main__":
    main()
