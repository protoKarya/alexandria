# Alexandria

The card catalog of the library that floats over MSU (42.73°N, 84.48°W).

Every page written for the investigation sites has one card here. Nothing was moved and nothing was
removed: the pages stay where they are published, and the card says what each one is.

- **class** - its Dewey number (`dewey.json`). `also_class` is a second subject when a work stands in two.
- **kind** - book, essay, letter, braid, person, network node, evidence, press coverage, finding aid.
- **place** - where the work lives on the globe (`places.json`). A work lives in Detroit only when it
  is about Detroit. A proof that uses Detroit as its example lives in the library and `touches` Detroit.
- **source** - the repository that holds the page; `also_in` lists other repositories with the same page.

| File | What it is |
| --- | --- |
| `shelves.md` | The catalog to read: every work under its class |
| `catalog.json` | The same cards for programs |
| `dewey.json` | The classes in use |
| `places.json` | Places and their coordinates |
| `overrides.json` | Corrections made by hand (create it when the first one is needed) |
| `tools/catalog.py` | Builds all of the above from the sites' `site/content` directories |

## This is a first pass

A program sorted these cards by section, title, tags and vocabulary. Records filed by section
(people, evidence, network, letters) are reliable. Essays were classed by the words they use, so
some are on the wrong shelf. To move one, add it to `overrides.json` and run the tool again:

```json
{"analysis/zksnark-proof.md": {"class": "510", "place": "library"}}
```

```
python tools/catalog.py --site amicusContra/tuebor=<path>/site/content --site defendDetroit/publicRecord=<path>/site/content
```

The first site named wins when both hold the same page.
