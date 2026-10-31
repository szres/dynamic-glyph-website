#!/usr/bin/env python3
"""Renumber tools/translations.json after the English pages gain or lose lines.

The translation ids are positions: every translatable element of the English
pages, in order (see build-i18n.py), then six head strings. When a line is
added or removed in the English pages, every later id moves. This script
compares the English lines of a git revision (default: HEAD) with the working
tree, keeps each unchanged line's translations under its new id, and takes
translations for new or changed lines from a JSON file you supply:

    {"ja": {"<new id>": "...", ...}, "zh-hans": {...}, "zh-hant": {...}}

Run:  python3 tools/renumber.py --new tools/new-lines.json [--base HEAD] [--dry]
It prints the new or changed ids it needs, rewrites translations.json and
tools/strings-en.md, and refuses to write if any translation is missing.
"""
import argparse
import difflib
import html
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("b", os.path.join(ROOT, "tools", "build-i18n.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
HEAD_COUNT = 6  # support title, privacy title, 3 descriptions, "Language"


def body_lines(read):
    out = []
    for page in b.PAGES:
        s = read(page)
        body = s[s.index("<body"):]
        body = re.sub(r"<!-- lang:start -->.*?<!-- lang:end -->", "", body, flags=re.S)
        for m in b.ELEM.finditer(body):
            if m.group(4) is not None:
                if m.group(4).strip():
                    out.append(html.unescape(m.group(4)))
                continue
            inner = m.group(3)
            if re.sub(r"<[^>]+>", "", inner).strip():
                out.append(to_md(inner))
    return out


def to_md(inner):
    t = re.sub(r"<strong>(.*?)</strong>", r"**\1**", inner, flags=re.S)
    t = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", t, flags=re.S)
    t = re.sub(r"<span>(.*?)</span>", r"\1", t)
    t = re.sub(r"<[^>]+>", "", t)
    return " ".join(html.unescape(t).split())


def head_lines(read):
    def title(p):
        return html.unescape(re.search(r"<title>(.*?)</title>", read(p), re.S).group(1))

    def desc(p):
        return html.unescape(re.search(r'<meta name="description" content="([^"]*)"', read(p)).group(1))
    return [title("support/index.html"), title("privacy/index.html"),
            desc("index.html"), desc("support/index.html"), desc("privacy/index.html"), "Language"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", help="JSON with translations for new or changed ids")
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    def read_base(p):
        return subprocess.check_output(["git", "-C", ROOT, "show", f"{a.base}:{p}"]).decode()

    def read_now(p):
        return open(os.path.join(ROOT, p)).read()

    old = body_lines(read_base) + head_lines(read_base)
    new = body_lines(read_now) + head_lines(read_now)
    ob, nb = len(old) - HEAD_COUNT, len(new) - HEAD_COUNT
    mapping, need = {}, []
    sm = difflib.SequenceMatcher(a=old[:ob], b=new[:nb], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mapping[j1 + k + 1] = i1 + k + 1
        else:
            need += list(range(j1 + 1, j2 + 1))
    for k in range(HEAD_COUNT):
        if old[ob + k] == new[nb + k]:
            mapping[nb + k + 1] = ob + k + 1
        else:
            need.append(nb + k + 1)

    print(f"English lines: {len(old)} -> {len(new)}")
    for n in need:
        print(f"  needs translation {n}: {new[n - 1][:90]}")
    tr = json.load(open(os.path.join(ROOT, "tools", "translations.json")))
    supplied = json.load(open(a.new)) if a.new else {}
    out, missing = {}, []
    for lang, t in tr.items():
        o = {}
        for n in range(1, len(new) + 1):
            if n in need:
                v = supplied.get(lang, {}).get(str(n))
                if v is None:
                    missing.append(f"{lang}:{n}")
                o[str(n)] = v
            else:
                o[str(n)] = t[str(mapping[n])]
        out[lang] = o
    if missing:
        print("missing:", " ".join(missing))
        sys.exit(1)
    if a.dry:
        return
    json.dump(out, open(os.path.join(ROOT, "tools", "translations.json"), "w"), ensure_ascii=False, indent=1)
    p = os.path.join(ROOT, "tools", "strings-en.md")
    head = open(p).read().split("\n1. ", 1)[0]
    with open(p, "w") as f:
        f.write(head + "\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(new, 1)) + "\n")
    print("wrote translations.json and strings-en.md")


if __name__ == "__main__":
    main()
