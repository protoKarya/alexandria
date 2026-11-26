#!/usr/bin/env python3
"""catalog.py - shelve every page of the library by Dewey class, kind, place and organ.

Nothing is moved and nothing is thrown away: every page gets one card. A card says what the work is
(its Dewey class, and a second class when it stands in two subjects), what kind of thing it is
(paper, notebook, essay, letter, person, evidence ...), where on the globe it lives, and which part
of the body it is: sporePrint is the nucleus, its science is the soul, and the hardware and the
Lansing Scuffle are the heart.

    python tools/catalog.py --centre ecoPrimals/sporePrint \
        --site ecoPrimals/sporePrint=<clone>/content \
        --site amicusContra/tuebor=<clone>/site/content \
        --site defendDetroit/publicRecord=<clone>/site/content=amicusContra/tuebor \
        --site amicusContra/lansing=<clone>/site/content

A third part (=other/repo) says "this site is a copy of that one": a page already carded from the
other site is not carded twice. Writes catalog.json, shelves.md, dewey.json and places.json in the
repo root. This is a machine's first pass: put corrections in overrides.json, keyed by
"owner/repo:path" ({"amicusContra/tuebor:analysis/zksnark-proof.md": {"place": "library"}}), and run it again.

Every card has a place, and place_by says how it was decided. A work lives where it is about. A case
record too short to be about anywhere goes by what it says of itself (a work of the commons belongs to
no one place: the library), then by its own subject tags, then with its full page, then with its
neighbours in the same folder. Only a record with none of these stays "unplaced".
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
    "003": ("Information, signals & systems", r"\b(signals?|information theory|compress\w+|noise|channels?|jitter|encod\w+|bandwidth|receptors?|sort|sorts|sorting)\b"),
    "004": ("Computing machines & hardware", r"\b(operating systems?|kernels?|gpus?|cpus?|npus?|chips?|silicon|hardware|servers?|boot\w*|firmware|linux|computers?|compute|vram|data cent(?:er|re)s?|neuromorphic)\b"),
    "005": ("Software & programming", r"\b(rust|code|compilers?|software|program\w*|crates?|binar\w+|open.source|repos?|repositor\w+|api|deploy\w*|pipelines?|primals?)\b"),
    "006": ("Artificial intelligence & rendering", r"\b(ai|a\.i\.|artificial intelligence|models?|agents?|llms?|neural|render\w*|shaders?|viewport|pixels?|surrogate)\b"),
    "016": ("Sources & bibliographies", None),
    "020": ("Libraries, archives & the commons", r"\b(librar\w+|archiv\w+|commons|public domain|catalog\w*|knowledge|public works|museum\w*|provenance)\b"),
    "025": ("Finding aids: how to walk the record", None),
    "040": ("Not yet shelved", None),
    "070": ("Press & journalism", r"\b(press|journalis\w+|reporters?|newsrooms?|coverage|media|headlines?|editors?|news)\b"),
    "110": ("Metaphysics & the cosmos", r"\b(cosmic|cosmos|universe|existence|reality|infinit\w+|ghosts?|soul|plato\w*|cave|eternal)\b"),
    "150": ("Psychology & attention", r"\b(addict\w+|attention|dopamine|feelings?|fear|trauma|psycholog\w+|behaviou?r\w*|grief|masks?|awareness)\b"),
    "170": ("Ethics & consent", r"\b(consent|ethic\w*|moral\w*|accountab\w+|stoic\w*|virtue|dignity|duty|invitation|gratitude|sovereign\w*)\b"),
    "290": ("Myth & religion", r"\b(gods?|myth\w*|bible|church\w*|sacred|olympus|prophets?|pray\w*|shepherds?|sheep|parable\w*|loaves|omelas)\b"),
    "320": ("Politics, capture & dark money", r"\b(dark money|lobby\w*|capture[ds]?|politic\w+|legislat\w+|senat\w+|governors?|elections?|campaigns?|pacs?|donors?)\b"),
    "330": ("Economics & extraction", r"\b(extract\w+|monopol\w+|profits?|bonds?|financ\w+|funding|funds?|money|markets?|invest\w+|billions?|wealth|econom\w+|competition|land deals?|real estate|tollbooth)\b"),
    "338": ("Enterprises & their networks", None),
    "340": ("Law", r"\b(law|laws|legal|courts?|judges?|rico|racketeer\w*|slapp|cease.and.desist|statutes?|indict\w*|plaintiffs?|defendants?|attorneys?|lawsuits?|convict\w*|damages|amicus|briefs?)\b"),
    "345": ("Evidence", None),
    "350": ("Public administration & agencies", r"\b(agenc\w+|departments?|emergency managers?|administrat\w+|regulat\w+|lara|oversight|audits?|foia|bureau\w*|officials?)\b"),
    "360": ("Social problems & child safety", r"\b(surveil\w+|privacy|data brokers?|safety|harms?|abus\w+|exploit\w+|welfare|poverty|kids|children|child|robocalls?|tracking)\b"),
    "370": ("Education", r"\b(schools?|charters?|educat\w+|literacy|teach\w+|students?|classrooms?|curricul\w+|universit\w+|academy|dpscd|faculty|mentor\w*)\b"),
    "500": ("Natural science, general", None),
    "501": ("Scientific method & validation", r"\b(falsif\w+|hypothes\w+|validat\w+|methodolog\w+|reproduc\w+|experiments?|benchmarks?|controls?|peer review|null)\b"),
    "510": ("Mathematics & proof", r"\b(proofs?|np|pnp|o\(1\)|complexit\w+|mathemat\w+|theorems?|topolog\w+|fractals?|pi|geometr\w+|geodesic|snarks?|zk|zero.knowledge|diameter|primes?|klein)\b"),
    "530": ("Physics", r"\b(physic\w+|anderson|localiz\w+|entropy|negentropy|protons?|electrons?|neutrinos?|neutrons?|quantum|qcd|plasma|yukawa|lattice|fermions?|thermodynam\w+|thermal|moore'?s law|permeab\w+|optics|diffract\w+)\b"),
    "540": ("Chemistry", r"\b(chemi\w+|molecul\w+|stoichiometr\w+|reactions?|enzym\w+|ferment\w*|adsorption|titrat\w+|synthase|polymerase)\b"),
    "550": ("Earth, water & weather", r"\b(soils?|water|drought|evapotranspiration|et0|infiltration|seismic|meteorolog\w+|climate|hydrolog\w+|penman|runoff)\b"),
    "570": ("Biology & living systems", r"\b(membranes?|mycel\w+|fung\w+|cells?|organisms?|epitopes?|immun\w+|biolog\w+|bees?|coral|species|evolution\w*|dna|genom\w+|ecosystems?|biosphere|yeast|microb\w+|quorum|16s|phenotype|lysogen\w+|algae)\b"),
    "610": ("Medicine & health", r"\b(clinic\w+|medic\w+|health\w*|hospitals?|covid|pandemic|plague|wounds?|cardio\w+|cysts?|diagnos\w+|patients?|doctors?|cancer|drugs?|disease)\b"),
    "620": ("Engineering & building", r"\b(engineer\w*|build\w*|machines?|infrastructure|fleet|tools?|stack|circuits?|beacons?|sensors?|iot)\b"),
    "630": ("Agriculture & field science", r"\b(crops?|yields?|irrigat\w+|till|no.?till|farms?|agricultur\w+|biochar|field|harvest\w*)\b"),
    "780": ("Music & song", r"\b(songs?|music\w*|bard|sing\w*|lyrics?|melod\w+|rhythm)\b"),
    "790": ("Games & play", r"\b(games?|gaming|play|players?|steam|valve|game devs?|bingo|bingocube|rpg)\b"),
    "816": ("Letters", None),
    "920": ("Lives & people", None),
    "940": ("World history", r"\b(france|europe\w*|rome|roman\w*|medieval|centur\w+|empires?|ancient|bones)\b"),
    "977": ("Michigan history & chronology", None),
}
# Sections whose class is fixed by what the section is.
SECTION_CLASS = {"actors": "920", "people": "920", "evidence": "345", "legal": "340", "coverage": "070", "timeline": "977", "network": "338", "sources": "016",
                 "open-letters": "816", "investigate": "025", "path": "025", "validate": "025", "explore": "025", "map": "025", "desk": "025", "site-index": "025",
                 "about": "025", "contact": "025", "signal": "025", "membrane": "025", "audience": "025", "glossary": "025", "site-map": "025",
                 "getting-started": "025", "collaborators": "920", "(top)": "025"}
# Sections whose class is found by vocabulary, with this class when the words say too little.
SECTION_FALLBACK = {"science": "500", "lab": "501", "thesis": "500", "methodology": "501", "guidestone": "501", "observatory": "501", "data": "020",
                    "architecture": "005", "technical": "005", "products": "005", "pseudospore": "005", "foundation": "005", "philosophy": "110",
                    "story": "920", "backstory": "920", "vision": "110", "outreach": "816"}
SECTION_KIND = {"actors": "person", "people": "person", "evidence": "evidence", "legal": "legal paper", "coverage": "press coverage", "network": "network node",
                "open-letters": "letter", "books": "book", "braid": "braid", "synthesis": "synthesis", "analysis": "essay",
                "science": "paper", "lab": "notebook", "thesis": "thesis chapter", "methodology": "method", "guidestone": "method", "architecture": "architecture note",
                "technical": "architecture note", "philosophy": "essay", "vision": "essay", "story": "essay", "backstory": "essay", "outreach": "outreach piece",
                "products": "product page", "data": "data sheet", "collaborators": "person"}
# An author's own "domain" line outranks vocabulary.
DOMAIN_CLASS = [(r"microbio|ecolog|biolog|immun|genom|membrane", "570"), (r"physic|material|plasma|qcd|optic|anderson", "530"), (r"chemi", "540"),
                (r"health|medic", "610"), (r"agricult|field", "630"), (r"game", "790"), (r"econom", "330"), (r"mathemat|geometr|category", "510"),
                (r"signal|information", "003"), (r"comput|infrastructure", "004"), (r"architecture", "005"), (r"methodolog|experiment|evolution", "501")]
LETTER_SLUG = re.compile(r"^(dear-|to-|cease-and-desist|letters?-|thank-you|open-letter)|_invitation$")
CHRONO_SLUG = re.compile(r"(chronolog|timeline|historical-pattern)")
SCUFFLE = re.compile(r"lansing\s+scuffle", re.I)
HARDWARE = re.compile(r"\b(hardware|gpus?|cpus?|npus?|silicon|neuromorphic|thermal|data cent(?:er|re)s?|compute)\b")

PLACES = {
    "library": {"name": "The Library, in HUD space above the Library of Congress, Washington DC - the nucleus, and works that belong to no one place", "lat": 38.8887, "lon": -77.0047},
    "lansing": {"name": "Lansing - the two houses of the Scuffle, and the Capitol", "lat": 42.7336, "lon": -84.5555},
    "detroit": {"name": "Detroit", "lat": 42.3314, "lon": -83.0458},
    "michigan": {"name": "Michigan, statewide", "lat": 44.3148, "lon": -85.6024},
    "unplaced": {"name": "Not yet placed - case records that name no Michigan place", "lat": None, "lon": None},
}
ORGANS = {"soul": "The science", "heart": "The hardware and the Lansing Scuffle"}
DET = re.compile(r"\b(detroit|wayne county|dpscd)\b", re.I)
LAN = re.compile(r"\b(lansing|ingham county|capitol)\b", re.I)
MICH = re.compile(r"\b(michigan)\b", re.I)
CASE_KINDS = ("network node", "evidence", "person", "press coverage", "legal paper")
# How a page of the commons marks itself: a Creator or Commons badge under its heading, or "commons" among its keywords.
COMMONS = re.compile(r"\*\*(?:Creator|Commons)\*\*|\*(?:creator|commons)\*")
COMMONS_TAG = re.compile(r"(^|,)\s*commons\s*(,|$)", re.I)


def front_matter(text):
    """Front matter as a dict, and the body. TOML between +++ lines, or simple YAML between --- lines."""
    text = text.lstrip("\ufeff")
    m = re.match(r"\s*\+\+\+\r?\n(.*?)\+\+\+", text, re.S)  # as Zola reads it: the closing +++ need not start a line
    if m:
        raw, body = m.group(1), text[m.end():]
        try:
            fm = tomllib.loads(raw)
        except Exception:
            # Not valid TOML (a few pages are not). Read the plain "key = value" lines; the first of each key is the page's own.
            fm = {}
            for k, v in re.findall(r"^([a-z_]+)\s*=\s*(.+)$", raw, re.M):
                fm.setdefault(k, re.findall(r'"([^"]*)"', v) if v.strip().startswith("[") else v.strip().strip('"'))
        for k in ("extra", "taxonomies"):
            if isinstance(fm.get(k), dict):
                for kk, vv in fm[k].items():
                    fm.setdefault(kk, vv)
        return fm, body
    m = re.match(r"\s*---\n(.*?)\n---", text.replace("\r\n", "\n"), re.S)
    if m:
        fm = {}
        for k, v in re.findall(r"^([A-Za-z_]+):\s*(.+)$", m.group(1), re.M):
            v = v.strip()
            fm[k.lower()] = re.findall(r'"([^"]*)"|\'([^\']*)\'', v) and [a or b for a, b in re.findall(r'"([^"]*)"|\'([^\']*)\'', v)] if v.startswith("[") else v.strip("\"'")
        return fm, text.replace("\r\n", "\n")[m.end():]
    return {}, text


def words_of(fm, keys):
    out = []
    for k in keys:
        v = fm.get(k)
        out.append(" ".join(map(str, v)) if isinstance(v, list) else str(v or ""))
    return " ".join(out)


def title_of(fm, body, slug):
    if fm.get("title"):
        return str(fm["title"])
    m = re.search(r"^#\s+(.+)$", body, re.M)
    return m.group(1).strip() if m else slug


def classify(section, slug, fm, body):
    """(class, second class or None, how it was decided)."""
    if section in SECTION_CLASS:
        return SECTION_CLASS[section], None, "by its section (%s/)" % section
    if LETTER_SLUG.search(slug):
        return "816", None, "it is a letter"
    if CHRONO_SLUG.search(slug):
        return "977", None, "it is a chronology"
    head = (words_of(fm, ("title", "subtitle", "description", "keywords", "tags")) + " " + re.sub(r"[-_]", " ", slug)).lower()
    n = max(len(body.split()), 300)
    scores = {}
    for code, (_, pattern) in DEWEY.items():
        if pattern:
            s = 6.0 * len(re.findall(pattern, head)) + 1000.0 * len(re.findall(pattern, body.lower())) / n
            if s:
                scores[code] = s
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    domain = str(fm.get("domain") or "").lower()
    for pattern, code in DOMAIN_CLASS:
        if domain and re.search(pattern, domain):
            second = next((c for c, _ in ranked if c != code), None)
            return code, second, "by the author's domain line"
    if not ranked or ranked[0][1] < 6.0:
        if section in SECTION_FALLBACK:
            return SECTION_FALLBACK[section], None, "by its section (%s/), the words said too little" % section
        return "040", None, "too little to go on"
    second = ranked[1][0] if len(ranked) > 1 and ranked[1][1] >= 0.6 * ranked[0][1] else None
    return ranked[0][0], second, "by its vocabulary"


def place_of(fm, body):
    """(home, places it merely touches). A work lives in a place only when it is ABOUT that place:
    named in the title or description, or named often for its length. A proof that uses Detroit as
    its worked example lives in the library and touches Detroit."""
    head = words_of(fm, ("title", "subtitle", "description"))
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


def anchor(fm, body):
    """(home, how) for a case record whose own page is not about a place. It goes by what the page says of
    itself: a work of the commons (Einstein, calculus, Tetris) belongs to no one place, which is the
    library; otherwise its own subject tags name the record it belongs to. A page that says neither stays
    unplaced here, and main() seats it with its full page or its neighbours."""
    if COMMONS.search(body[:400]) or COMMONS_TAG.search(str(fm.get("keywords") or "")):
        return "library", "it is of the commons"
    tags = words_of(fm, ("keywords", "counties", "tags", "role"))  # role: the one line a graph stub says of itself
    d, l = len(DET.findall(tags)), len(LAN.findall(tags))
    if d or l:
        return ("detroit" if d > l else "lansing" if l > d else "michigan"), "by its own subject tags"
    if MICH.search(tags) or fm.get("counties"):
        return "michigan", "by its own subject tags"
    return "unplaced", None


def seat_the_rest(cards):
    """Case records that say nothing of place (mostly the 11-word stubs of the network graph). A stub sits
    where its full page sits; failing that, where most of its folder sits, counting only neighbours that
    were placed by their own words."""
    loose = [c for c in cards.values() if c["place"] == "unplaced"]

    def lead(c):
        return c["title"].lower().split(" \u2014 ")[0].strip()

    for c in loose:
        twins = [x for x in cards.values() if x is not c and x["source"] == c["source"] and x["place"] != "unplaced" and lead(x) == lead(c)]
        twin = min(twins, key=lambda x: (x["path"].split("/")[0] != c["path"].split("/")[0], x["path"])) if twins else None  # its own section first
        if twin:
            c["place"], c["place_by"] = twin["place"], "with its full page (%s)" % twin["path"]
    for c in loose:
        if c["place"] != "unplaced":
            continue
        folder = c["path"].rsplit("/", 1)[0] if "/" in c["path"] else ""
        votes = {}
        for x in cards.values():
            if x["source"] == c["source"] and x["path"].startswith(folder + "/") and x["path"].count("/") == c["path"].count("/") \
                    and x["place"] in ("detroit", "lansing", "michigan") and x["place_by"] in ("by what it says", "by its own subject tags"):
                votes[x["place"]] = votes.get(x["place"], 0) + 1
        if votes:
            ranked = sorted(votes, key=lambda p: -votes[p])
            # An even split between two places is settled by the state, which holds them both.
            c["place"] = "michigan" if len(ranked) > 1 and votes[ranked[0]] == votes[ranked[1]] else ranked[0]
            c["place_by"] = "with its neighbours in %s/ (%s)" % (folder, ", ".join("%s %d" % kv for kv in sorted(votes.items(), key=lambda kv: -kv[1])))


def kind_of(section, slug):
    if slug == "_index":
        return "front page"
    if LETTER_SLUG.search(slug) and section not in SECTION_CLASS:
        return "letter"
    return SECTION_KIND.get(section, "finding aid")


def repo_prefix(content):
    """Path of the content directory inside its repository, e.g. 'site/content'."""
    d, parts = os.path.abspath(content), []
    while d and not os.path.exists(os.path.join(d, ".git")):
        parts.insert(0, os.path.basename(d))
        nd = os.path.dirname(d)
        if nd == d:
            return os.path.basename(os.path.abspath(content))
        d = nd
    return "/".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="append", required=True, help="owner/repo=path to its content directory[=owner/repo it is a copy of]")
    ap.add_argument("--centre", help="owner/repo that is the nucleus of the library")
    args = ap.parse_args()
    overrides = {}
    if os.path.exists(os.path.join(ROOT, "overrides.json")):
        overrides = json.load(open(os.path.join(ROOT, "overrides.json"), encoding="utf-8"))
    cards, sources = {}, []
    for spec in args.site:
        label, content, copy_of = (spec.split("=") + [""])[:3]
        prefix = repo_prefix(content)
        sources.append(label)
        for base, dirs, files in os.walk(content):
            dirs.sort()
            for f in sorted(files):
                if not f.endswith(".md"):
                    continue
                full = os.path.join(base, f)
                rel = os.path.relpath(full, content).replace("\\", "/")
                if copy_of and (copy_of + ":" + rel) in cards:
                    cards[copy_of + ":" + rel]["also_in"].append(label)
                    continue
                raw = open(full, "rb").read()
                fm, body = front_matter(raw.decode("utf-8", "replace"))
                slug = f[:-3]
                if slug == "_index" and len(body.split()) < 100:
                    continue  # a bare section heading, not a page
                section = rel.split("/")[0] if "/" in rel else "(top)"
                cls, second, how = classify(section, slug, fm, body)
                kind = kind_of(section, slug)
                home, touches = place_of(fm, body)
                place_by = "by what it says"
                if home == "library" and kind in CASE_KINDS and label != args.centre:
                    home, place_by = anchor(fm, body)  # a case record is not a library work just because it names no city
                title = title_of(fm, body, slug)
                # Heart: the work names the Lansing Scuffle, or it is a nucleus work whose own title, subtitle or keywords are about the hardware.
                organ = None
                if SCUFFLE.search(title + " " + body):
                    organ = "heart"
                elif label == args.centre:
                    head = (words_of(fm, ("title", "subtitle", "keywords")) + " " + re.sub(r"[-_]", " ", slug)).lower()
                    organ = "heart" if HARDWARE.search(head) else "soul"
                if label == args.centre:
                    home, touches = ("lansing" if organ == "heart" else "library"), [t for t in set(touches + [home]) if t in ("detroit", "lansing", "michigan")]
                    touches = sorted(t for t in touches if t != home)
                    place_by = "it is the nucleus"
                paper = re.match(r"(\d+)_", slug) if section == "science" else None
                card = {"id": label + ":" + rel, "path": rel, "title": title[:160], "class": cls, "also_class": second, "kind": kind,
                        "organ": organ, "nucleus": label == args.centre, "place": home, "place_by": place_by, "touches": touches,
                        "paper": int(paper.group(1)) if paper else None, "date": str(fm.get("date") or "")[:10], "words": len(body.split()),
                        "sorted": how, "source": label, "also_in": [], "sha256": hashlib.sha256(raw).hexdigest(),
                        "url": "https://github.com/%s/blob/main/%s/%s" % (label, prefix, rel)}
                if fm.get("slug"):
                    card["slug"] = str(fm["slug"])  # the page says where it is published: its last name on the site is this, not its file's name
                fix = overrides.get(card["id"]) or overrides.get(rel)
                if fix:
                    card.update(fix)
                    if "place" in fix:
                        card["place_by"] = fix.get("place_by") or "by hand (overrides.json)"
                    if set(fix) - {"place", "place_by", "touches"}:
                        card["sorted"] = "by hand (overrides.json)"
                cards[card["id"]] = card
    seat_the_rest(cards)
    cards = sorted(cards.values(), key=lambda c: (c["class"], not c["nucleus"], c["paper"] if c["paper"] is not None else 10 ** 6, c["title"].lower()))

    def dump(name, obj):
        with open(os.path.join(ROOT, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)

    dump("dewey.json", {code: name for code, (name, _) in DEWEY.items()})
    dump("places.json", PLACES)
    dump("catalog.json", {"note": "First pass, sorted by machine. Nothing was moved; every page has one card. Corrections go in overrides.json.",
                          "centre": args.centre, "organs": ORGANS, "sources": sources, "cards": cards})
    by_class, by_place, by_organ = {}, {}, {}
    for c in cards:
        by_class.setdefault(c["class"], []).append(c)
        by_place[c["place"]] = by_place.get(c["place"], 0) + 1
        if c["organ"]:
            by_organ.setdefault(c["organ"], []).append(c)
    nucleus = [c for c in cards if c["nucleus"]]

    def line(c):
        return "- [%s](%s) - %s, %s, %d words%s%s\n" % (c["title"].replace("[", "(").replace("]", ")"), c["url"], c["kind"], c["place"], c["words"],
                                                         (", also %s" % c["also_class"]) if c["also_class"] else "", (", **%s**" % c["organ"]) if c["organ"] else "")

    with open(os.path.join(ROOT, "shelves.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# The shelves\n\nFirst pass, sorted by machine: %d works, nothing moved. Fix a card in `overrides.json` and run `tools/catalog.py` again.\n\n" % len(cards))
        if args.centre:
            f.write("## The nucleus: %s\n\n%d works, %d words. Everything else is shelved around it.\n\n" % (args.centre, len(nucleus), sum(c["words"] for c in nucleus)))
            f.write("- **Soul - the science:** %d works in the library above the Library of Congress.\n" % len(by_organ.get("soul", [])))
            f.write("- **Heart - the hardware and the Lansing Scuffle:** %d works in Lansing.\n\n" % len(by_organ.get("heart", [])))
            f.write("### The heart\n\n")
            for c in sorted(by_organ.get("heart", []), key=lambda c: (not SCUFFLE.search(c["title"]), not c["nucleus"], c["title"].lower())):
                f.write(line(c))
            f.write("\n")
        f.write("Where the works live: " + ", ".join("%s %d" % (PLACES[p]["name"].split(",")[0].split(" - ")[0], n) for p, n in sorted(by_place.items(), key=lambda kv: -kv[1])) + ".\n")
        for code in sorted(by_class):
            f.write("\n## %s %s (%d)\n\n" % (code, DEWEY[code][0], len(by_class[code])))
            for c in by_class[code]:
                f.write(line(c))
    print("%d works shelved; nucleus %d (soul %d, heart %d); heart outside the nucleus %d" % (
        len(cards), len(nucleus), sum(1 for c in nucleus if c["organ"] == "soul"), sum(1 for c in nucleus if c["organ"] == "heart"),
        sum(1 for c in by_organ.get("heart", []) if not c["nucleus"])))
    for code in sorted(by_class):
        cs = by_class[code]
        kinds = sorted({k: sum(1 for c in cs if c["kind"] == k) for k in {c["kind"] for c in cs}}.items(), key=lambda kv: -kv[1])[:4]
        print("  %s %-38s %4d  nucleus %3d   %s" % (code, DEWEY[code][0], len(cs), sum(1 for c in cs if c["nucleus"]), ", ".join("%s %d" % kv for kv in kinds)))
    print("where they live: " + ", ".join("%s %d" % kv for kv in sorted(by_place.items(), key=lambda kv: -kv[1])))
    print("by source: " + ", ".join("%s %d" % (s, sum(1 for c in cards if c["source"] == s)) for s in sources))
    return 0


if __name__ == "__main__":
    sys.exit(main())
