# Alexandria

The card catalog of the library. On the globe it sits in HUD space above the Library of Congress in
Washington DC (38.89°N, 77.00°W).

Every page of the library has one card here. Nothing was moved and nothing was removed: the pages
stay where they are published, and the card says what each one is.

## The nucleus

[sporePrint](https://github.com/ecoPrimals/sporePrint) is the centre. Everything else is shelved around it.

- **Soul - the science.** The papers, notebooks, thesis and methods of sporePrint. They live in the library.
- **Heart - the hardware and the Lansing Scuffle.** Paper 110, every work that names the Scuffle, and
  the sporePrint works whose own title is about the hardware. They live in Lansing, in the two houses.

## What a card says

- **class** - its Dewey number (`dewey.json`). `also_class` is a second subject when a work stands in two.
- **kind** - paper, notebook, thesis chapter, method, essay, book, letter, braid, person, network node, evidence, finding aid.
- **organ** - `soul` or `heart`, or nothing. **nucleus** - true for sporePrint's own pages.
- **place** - where the work lives on the globe (`places.json`). A work lives in Detroit only when it
  is about Detroit. A proof that uses Detroit as its example lives in the library and `touches` Detroit.
- **source** - the repository that holds the page; `also_in` lists other repositories with the same page.

| File | What it is |
| --- | --- |
| `shelves.md` | The catalog to read: the nucleus and the heart first, then every work under its class |
| `catalog.json` | The same cards for programs |
| `dewey.json` | The classes in use |
| `places.json` | Places and their coordinates |
| `overrides.json` | Corrections made by hand (create it when the first one is needed) |
| `tools/catalog.py` | Builds all of the above from the sites' content directories |

## This is a first pass

A program sorted these cards. Records filed by section (people, evidence, network, letters) are
reliable, and so are papers whose author wrote a `domain` line. The rest were classed by the words
they use, so some are on the wrong shelf. To move one, add it to `overrides.json` and run the tool again:

```json
{"amicusContra/tuebor:analysis/zksnark-proof.md": {"place": "library"}}
```

```
python tools/catalog.py --centre ecoPrimals/sporePrint \
    --site ecoPrimals/sporePrint=<clone>/content \
    --site amicusContra/tuebor=<clone>/site/content \
    --site defendDetroit/publicRecord=<clone>/site/content=amicusContra/tuebor \
    --site amicusContra/lansing=<clone>/site/content
```

A third part on a `--site` marks that site as a copy of another: a page already carded from the
other site is not carded twice.
