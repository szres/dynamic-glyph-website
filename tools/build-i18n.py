#!/usr/bin/env python3
"""Build the ja / zh-hans / zh-hant copies of the site from the English pages.

The English pages at the root are the source. Every translatable line is
numbered in the same order as tools/strings-en.md (h1/h2/h3/p/li text and img
alt, then page titles and descriptions). Translations live in
tools/translations.json as {"ja": {"1": "...", ...}, ...}, written in the same
light markdown: [text](href) for links, **text** for bold.

Run: python3 tools/build-i18n.py   (writes ja/, zh-hans/, zh-hant/ and
refreshes the language switcher on every page). The output is committed; the
site itself has no build step.
"""
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index.html", "support/index.html", "privacy/index.html"]
LANGS = [("en", "", "English"), ("ja", "ja/", "日本語"),
         ("zh-hans", "zh-hans/", "简体中文"), ("zh-hant", "zh-hant/", "繁體中文")]
HTML_LANG = {"en": "en", "ja": "ja", "zh-hans": "zh-Hans", "zh-hant": "zh-Hant"}
SCREENS = {"zh-hans": "zh-hans/"}  # localized captures; others use English ones
ELEM = re.compile(r'<(h1|h2|h3|p|li)(\s[^>]*)?>(.*?)</\1>|<img[^>]*alt="([^"]*)"', re.S)
META_KEYS = {  # page -> (title key, description key)
    "index.html": (None, 98),
    "support/index.html": (96, 99),
    "privacy/index.html": (97, 100),
}


def md_to_html(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def switcher(page, current):
    items = []
    for code, prefix, label in LANGS:
        href = "/" + prefix + page.replace("index.html", "")
        if code == current:
            items.append(f'<li><span aria-current="true">{label}</span></li>')
        else:
            items.append(f'<li><a href="{href}" hreflang="{HTML_LANG[code]}" lang="{HTML_LANG[code]}">{label}</a></li>')
    return ('<!-- lang:start -->\n    <ul class="langs" aria-label="{L}">\n      '
            + "\n      ".join(items) + "\n    </ul>\n    <!-- lang:end -->")


def alternates(page):
    links = [f'<link rel="alternate" hreflang="{HTML_LANG[c]}" href="https://glyph.szres.org/{p}{page.replace("index.html", "")}">'
             for c, p, _ in LANGS]
    links.append(f'<link rel="alternate" hreflang="x-default" href="https://glyph.szres.org/{page.replace("index.html", "")}">')
    return "<!-- alt:start -->\n" + "\n".join(links) + "\n<!-- alt:end -->"


def put_blocks(s, page, lang, label):
    sw = switcher(page, lang).replace("{L}", label)
    s = re.sub(r"<!-- lang:start -->.*?<!-- lang:end -->", sw, s, flags=re.S)
    s = re.sub(r"<!-- alt:start -->.*?<!-- alt:end -->", alternates(page), s, flags=re.S)
    return s


def main():
    tr = json.load(open(os.path.join(ROOT, "tools", "translations.json")))
    # English: refresh switcher and alternates only.
    for page in PAGES:
        p = os.path.join(ROOT, page)
        s = open(p).read()
        open(p, "w").write(put_blocks(s, page, "en", "Language"))

    todo = [l for l in LANGS[1:] if l[0] in tr]
    if "en" in tr:  # corrected English source: rewrite the root pages first
        todo = [LANGS[0]] + todo
    for code, prefix, _ in todo:
        t = tr[code]
        n = 0
        for page in PAGES:
            s = open(os.path.join(ROOT, page)).read()
            head, body = s[: s.index("<body")], s[s.index("<body"):]

            def sub(m):
                nonlocal n
                if m.group(4) is not None:
                    if not m.group(4).strip():
                        return m.group(0)
                    n += 1
                    return m.group(0).replace(f'alt="{m.group(4)}"', f'alt="{html.escape(t[str(n)])}"')
                inner = m.group(3)
                if not re.sub(r"<[^>]+>", "", inner).strip():
                    return m.group(0)
                n += 1
                new = md_to_html(t[str(n)])
                if m.group(1) == "h1" and "<span>" in inner:  # "Dynamic Glyph <span>for Ingress</span>"
                    before, _, after = new.partition("Dynamic Glyph")
                    new = ((f"<span>{before.strip()}</span> " if before.strip() else "")
                           + "Dynamic Glyph" + (f" <span>{after.strip()}</span>" if after.strip() else ""))
                return f"<{m.group(1)}{m.group(2) or ''}>{new}</{m.group(1)}>"

            body = re.sub(r"<!-- lang:start -->.*?<!-- lang:end -->", "<!-- lang:start --><!-- lang:end -->", body, flags=re.S)
            body = ELEM.sub(sub, body)
            tk, dk = META_KEYS[page]
            if tk:
                head = re.sub(r"<title>.*?</title>", f"<title>{html.escape(t[str(tk)])}</title>", head)
            head = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + html.escape(t[str(dk)]), head)
            if page == "index.html" and code != "en":
                head = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + html.escape(t["3"]), head)
            s = head.replace('<html lang="en">', f'<html lang="{HTML_LANG[code]}">') + body
            if code != "en":  # shared files live at the root: one more level up
                s = re.sub(r'(href|src|srcset)="((?:\.\./)*)assets/', r'\1="../\2assets/', s)
            s = s.replace("assets/app-store-badge-en.svg", f"assets/app-store-badge-{code}.svg")
            if code in SCREENS:
                s = s.replace("assets/screens/", "assets/screens/" + SCREENS[code])
            s = put_blocks(s, page, code, t["101"])
            out = os.path.join(ROOT, prefix, page)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, "w").write(s)
        print(code, "lines used:", n)


if __name__ == "__main__":
    main()
