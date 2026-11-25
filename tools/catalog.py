#!/usr/bin/env python3
"""catalog.py - shelve every page of the investigation sites by Dewey class, kind and place.

Nothing is moved and nothing is thrown away: every page gets one card. A card says what the work is
(its Dewey class, and a second class when it stands in two subjects), what kind of thing it is
(book, essay, letter, person, evidence ...), and where on the globe it belongs - which is often
NOT Detroit.

    python tools/catalog.py --site amicusContra/tuebor=<path to site/content> \
                            --site defendDetroit/publicRecord=<path to site/content>

The first site named wins when the same page is in both. Writes catalog.json and shelves.md in the
repo root. This is a machine's first pass: put corrections in overrides.json
({"analysis/zksnark-proof.md": {"class": "510", "place": "library"}}) and run it again.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dewey classes used here: number -> (name, vocabulary that marks the subject). None = shelved by rule, not by vocabulary.
DEWEY = {
    "004": ("Computing, machines & operating systems", r"\b(operating systems?|kernels?|gpus?|cpus?|chips?|silicon|hardware|servers?|boot\w*|firmware|linux|computers?|compute)\b"),
    "005": ("Software & programming", r"\b(rust|code|compilers?|software|program\w*|crates?|binar\w+|open.source|repos?|repositor\w+|api)\b"),
    "006": ("Artificial intelligence & rendering", r"\b(ai|a\.i\.|artificial intelligence|models?|agents?|llms?|neural|render\w*|shaders?|viewport|pixels?)\b"),
    "016": ("Sources & bibliographies", None),
    "020": ("Libraries, archives & the commons", r"\b(librar\w+|archiv\w+|commons|public domain|catalog\w*|knowledge|public works|museum\w*)\b"),
    "025": ("Finding aids: how to walk the record", None),
    "040": ("Not yet shelved", None),
    "070": ("Press & journalism", r"\b(press|journalis\w+|reporters?|newsrooms?|coverage|media|headlines?|editors?|news)\b"),
    "110": ("Metaphysics & the cosmos", r"\b(cosmic|cosmos|universe|existence|reality|infinit\w+|ghosts?|soul|plato\w*|cave|eternal)\b"),
    "150": ("Psychology & attention", r"\b(addict\w+|attention|dopamine|feelings?|fear|trauma|psycholog\w+|behaviou?r\w*|grief|masks?)\b"),
    "170": ("Ethics & consent", r"\b(consent|ethic\w*|moral\w*|accountab\w+|stoic\w*|virtue|dignity|duty|invitation|gratitude)\b"),
    "290": ("Myth & religion", r"\b(gods?|myth\w*|bible|church\w*|sacred|olympus|prophets?|pray\w*|shepherds?|sheep|parable\w*)\b"),
    "320": ("Politics, capture & dark money", r"\b(dark money|lobby\w*|capture[ds]?|politic\w+|legislat\w+|senat\w+|governors?|elections?|campaigns?|pacs?|donors?)\b"),
    "330": ("Economics & extraction", r"\b(extract\w+|monopol\w+|profits?|bonds?|financ\w+|funding|funds?|money|markets?|invest\w+|billions?|wealth|econom\w+|competition|land deals?|real estate)\b"),
    "338": ("Enterprises & their networks", None),
    "340": ("Law", r"\b(law|laws|legal|courts?|judges?|rico|racketeer\w*|slapp|cease.and.desist|statutes?|indict\w*|plaintiffs?|defendants?|attorneys?|lawsuits?|convict\w*|damages|amicus|briefs?)\b"),
    "345": ("Evidence", None),
    "350": ("Public administration & agencies", r"\b(agenc\w+|departments?|emergency managers?|administrat\w+|regulat\w+|lara|oversight|audits?|foia|bureau\w*|officials?)\b"),
    "360": ("Social problems & child safety", r"\b(surveil\w+|privacy|data brokers?|safety|harms?|abus\w+|exploit\w+|welfare|poverty|kids|children|child|robocalls?|tracking)\b"),
    "370": ("Education", r"\b(schools?|charters?|educat\w+|literacy|teach\w+|students?|classrooms?|curricul\w+|universit\w+|academy|dpscd)\b"),
    "510": ("Mathematics & proof", r"\b(proofs?|np|o\(1\)|complexit\w+|mathemat\w+|theorems?|topolog\w+|fractals?|pi|geometr\w+|snarks?|zk|zero.knowledge|diameter)\b"),
    "530": ("Physics", r"\b(physic\w+|anderson|localiz\w+|entropy|negentropy|protons?|electrons?|neutrinos?|neutrons?|quantum|thermodynam\w+|moore'?s law|permeab\w+)\b"),
    "570": ("Biology & living systems", r"\b(membranes?|mycel\w+|fung\w+|cells?|organisms?|epitopes?|immun\w+|biolog\w+|bees?|coral|species|evolution\w*|dna|genom\w+|ecosystems?|biosphere|yeast)\b"),
    "610": ("Medicine & health", r"\b(clinic\w+|medic\w+|health\w*|hospitals?|covid|pandemic|plague|wounds?|cardio\w+|cysts?|diagnos\w+|patients?|doctors?)\b"),
    "620": ("Engineering & building", r"\b(engineer\w*|build\w*|machines?|infrastructure|fleet|tools?|stack|circuits?|beacons?)\b"),
    "780": ("Music & song", r"\b(songs?|music\w*|bard|sing\w*|lyrics?|melod\w+|rhythm)\b"),
    "790": ("Games & play", r"\b(games?|gaming|play|players?|steam|valve|game devs?|bingo)\b"),
    "816": ("Letters", None),
    "920": ("Lives & people", None),
    "940": ("World history", r"\b(france|europe\w*|rome|roman\w*|medieval|centur\w+|empires?|ancient|bones)\b"),
    "977": ("Michigan history & chronology", None),
}
SECTION_CLASS = {"actors": "920", "people": "920", "evidence": "345", "legal": "340", "coverage": "070", "timeline": "977", "network": "338", "sources": "016",
                 "open-letters": "816", "investigate": "025", "path": "025", "validate": "025", "explore": "025", "map": "025", "desk": "025", "site-index": "025",
                 "about": "025", "contact": "025", "signal": "025", "membrane": "025"}
SECTION_KIND = {"actors": "person", "people": "person", "evidence": "evidence", "legal": "legal paper", "coverage": "press coverage", "network": "network node",
                "open-letters": "letter", "books": "book", "braid": "braid", "synthesis": "synthesis"}
LETTER_SLUG = re.compile(r"^(dear-|to-|cease-and-desist|letters?-|thank-you|open-letter)")
CHRONO_SLUG = re.compile(r"(chronolog|timeline|historical-pattern)")

PLACES = {
    "detroit": {"name": "Detroit", "lat": 42.3314, "lon": -83.0458},
    "lansing": {"name": "Lansing (the Capitol)", "lat": 42.7336, "lon": -84.5555},
    "michigan": {"name": "Michigan, statewide", "lat": 44.3148, "lon": -85.6024},
    "library": {"name": "The Library, floating over MSU - works that belong to no one place", "lat": 42.7325, "lon": -84.4822},
    "unplaced": {"name": "Not yet placed - case records that name no Michigan place", "lat": None, "lon": None},
}
DET = re.compile(r"\b(detroit|wayne county|dpscd)\b", re.I)
LAN = re.compile(r"\b(lansing|ingham county|capitol)\b", re.I)
MICH = re.compile(r"\b(michigan)\b", re.I)


def front_matter(text):
    m = re.match(r"\s*\+\+\+(.*?)\+\+\+", text, re.S)
    if not m:
        return {}, text
    raw, body = m.group(1), text[m.end():]
    try:
        fm = tomllib.loads(raw)
    except Exception:
        fm = {}
        for k, v in re.findall(r"^([a-z_]+)\s*=\s*(.+)$", raw, re.M):
            fm[k] = re.findall(r'"([^"]*)"', v) if v.strip().startswith("[") else v.strip().strip('"')
    for k in ("extra", "taxonomies"):
        if isinstance(fm.get(k), dict):
            for kk, vv in fm[k].items():
                fm.setdefault(kk, vv)
    return fm, body


def words_of(fm, keys):
    out = []
    for k in keys:
        v = fm.get(k)
        out.append(" ".join(map(str, v)) if isinstance(v, list) else str(v or ""))
    return " ".join(out)


def classify(section, slug, fm, body):
    """(class, second class or None, how it was decided)."""
    if section in SECTION_CLASS:
        return SECTION_CLASS[section], None, "by its section (%s/)" % section
    if LETTER_SLUG.match(slug):
        return "816", None, "it is a letter"
    if CHRONO_SLUG.search(slug):
        return "977", None, "it is a chronology"
    head = (words_of(fm, ("title", "description", "keywords", "tags")) + " " + slug.replace("-", " ")).lower()
    n = max(len(body.split()), 300)
    scores = {}
    for code, (_, pattern) in DEWEY.items():
        if pattern:
            s = 6.0 * len(re.findall(pattern, head)) + 1000.0 * len(re.findall(pattern, body.lower())) / n
            if s:
                scores[code] = s
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < 6.0:
        return "040", None, "too little to go on"
    second = ranked[1][0] if len(ranked) > 1 and ranked[1][1] >= 0.6 * ranked[0][1] else None
    return ranked[0][0], second, "by its vocabulary"


def place_of(fm, body):
    """(home, places it merely touches). A work lives in a place only when it is ABOUT that place:
    named in the title or description, or named often for its length. A proof that uses Detroit as
    its worked example lives in the library and touches Detroit."""
    head = words_of(fm, ("title", "description"))
    text = head + " " + words_of(fm, ("keywords", "counties")) + " " + body
    per = 1000.0 / max(len(body.split()), 300)
    found = {"detroit": len(DET.findall(text)), "lansing": len(LAN.findall(text)), "michigan": len(MICH.findall(text))}
    about = {"detroit": bool(DET.search(head)), "lansing": bool(LAN.search(head)), "michigan": bool(MICH.search(head))}
    touches = [p for p in ("detroit", "lansing", "michigan") if found[p]]
    for p in ("detroit", "lansing"):
        other = found["lansing" if p == "detroit" else "detroit"]
        if found[p] >= 2 * other and (about[p] or (found[p] >= 3 and found[p] * per >= 4.0)):
            return p, [t for t in touches if t != p]
    if about["michigan"] or (sum(found.values()) >= 4 and sum(found.values()) * per >= 4.0):
        return "michigan", [t for t in touches if t != "michigan"]
    return "library", touches


def kind_of(section, slug):
    if section in SECTION_KIND:
        return SECTION_KIND[section]
    if LETTER_SLUG.match(slug):
        return "letter"
    return "essay" if section in ("analysis",) else "finding aid"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="append", required=True, help="owner/repo=path to its site/content directory (first one wins)")
    args = ap.parse_args()
    overrides = {}
    if os.path.exists(os.path.join(ROOT, "overrides.json")):
        overrides = json.load(open(os.path.join(ROOT, "overrides.json"), encoding="utf-8"))
    cards = {}
    for spec in args.site:
        label, _, content = spec.partition("=")
        for base, _, files in os.walk(content):
            for f in sorted(files):
                if not f.endswith(".md") or f == "_index.md":
                    continue
                full = os.path.join(base, f)
                rel = os.path.relpath(full, content).replace("\\", "/")
                if rel in cards:
                    cards[rel]["also_in"].append(label)
                    continue
                raw = open(full, "rb").read()
                fm, body = front_matter(raw.decode("utf-8", "replace"))
                section, slug = (rel.split("/")[0] if "/" in rel else "(top)"), f[:-3]
                cls, second, how = classify(section, slug, fm, body)
                home, touches = place_of(fm, body)
                if home == "library" and kind_of(section, slug) in ("network node", "evidence", "person", "press coverage", "legal paper"):
                    home = "unplaced"  # a case record is not a library work just because it names no city
                card = {"path": rel, "title": str(fm.get("title") or slug)[:160], "class": cls, "also_class": second, "kind": kind_of(section, slug),
                        "place": home, "touches": touches, "date": str(fm.get("date") or "")[:10], "words": len(body.split()), "sorted": how,
                        "source": label, "also_in": [], "sha256": hashlib.sha256(raw).hexdigest(),
                        "url": "https://github.com/%s/blob/main/site/content/%s" % (label, rel)}
                if rel in overrides:
                    card.update(overrides[rel])
                    card["sorted"] = "by hand (overrides.json)"
                cards[rel] = card
    cards = sorted(cards.values(), key=lambda c: (c["class"], c["title"].lower()))
    with open(os.path.join(ROOT, "dewey.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({code: name for code, (name, _) in DEWEY.items()}, f, indent=1)
    with open(os.path.join(ROOT, "places.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(PLACES, f, indent=1)
    with open(os.path.join(ROOT, "catalog.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"note": "First pass, sorted by machine. Nothing was moved; every page has one card. Corrections go in overrides.json.",
                   "sources": [s.split("=")[0] for s in args.site], "cards": cards}, f, indent=1, ensure_ascii=False)
    by_class, by_place = {}, {}
    for c in cards:
        by_class.setdefault(c["class"], []).append(c)
        by_place[c["place"]] = by_place.get(c["place"], 0) + 1
    with open(os.path.join(ROOT, "shelves.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# The shelves\n\nFirst pass, sorted by machine: %d works, nothing moved. Fix a card in `overrides.json` and run `tools/catalog.py` again.\n\n" % len(cards))
        f.write("Where they belong: " + ", ".join("%s %d" % (PLACES[p]["name"].split(",")[0].split(" - ")[0], n) for p, n in sorted(by_place.items(), key=lambda kv: -kv[1])) + ".\n")
        for code in sorted(by_class):
            f.write("\n## %s %s (%d)\n\n" % (code, DEWEY[code][0], len(by_class[code])))
            for c in by_class[code]:
                f.write("- [%s](%s) - %s, %s, %d words%s\n" % (c["title"].replace("[", "(").replace("]", ")"), c["url"], c["kind"], c["place"], c["words"],
                                                                (", also %s" % c["also_class"]) if c["also_class"] else ""))
    print("%d works shelved" % len(cards))
    for code in sorted(by_class):
        cs = by_class[code]
        print("  %s %-42s %4d   %s" % (code, DEWEY[code][0], len(cs), ", ".join("%s %d" % kv for kv in sorted({k: sum(1 for c in cs if c["kind"] == k) for k in {c["kind"] for c in cs}}.items(), key=lambda kv: -kv[1])[:4])))
    print("where they belong: " + ", ".join("%s %d" % kv for kv in sorted(by_place.items(), key=lambda kv: -kv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
