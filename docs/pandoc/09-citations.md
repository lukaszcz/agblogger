# 9 Citations

When the `--citeproc` option is used, pandoc can automatically generate citations and a bibliography in a number of styles. Basic usage is:

```
pandoc --citeproc myinput.txt
```

To use this feature, you will need to have:

- a document containing citations (see Citation syntax);
- a source of bibliographic data: either an external bibliography file or a list of `references` in the document's YAML metadata;
- optionally, a [CSL](https://docs.citationstyles.org/en/stable/specification.html) citation style.

---

## 9.1 Specifying bibliographic data

You can specify an external bibliography using the `bibliography` metadata field in a YAML metadata section or the `--bibliography` command line argument. If you want to use multiple bibliography files, you can supply multiple `--bibliography` arguments or set `bibliography` metadata field to YAML array. A bibliography may have any of these formats:

| Format | File extension |
|--------|----------------|
| BibLaTeX | .bib |
| BibTeX | .bibtex |
| CSL JSON | .json |
| CSL YAML | .yaml |
| RIS | .ris |

Note that `.bib` can be used with both BibTeX and BibLaTeX files; use the extension `.bibtex` to force interpretation as BibTeX.

In BibTeX and BibLaTeX databases, pandoc parses LaTeX markup inside fields such as `title`; in CSL YAML databases, pandoc Markdown; and in CSL JSON databases, an HTML-like markup:

| Syntax | Effect |
|--------|--------|
| `<i>...</i>` | italics |
| `<b>...</b>` | bold |
| `<span style="font-variant:small-caps;">...</span>` or `<sc>...</sc>` | small capitals |
| `<sub>...</sub>` | subscript |
| `<sup>...</sup>` | superscript |
| `<span class="nocase">...</span>` | prevent a phrase from being capitalized as title case |

As an alternative to specifying a bibliography file using `--bibliography` or the YAML metadata field `bibliography`, you can include the citation data directly in the `references` field of the document's YAML metadata. The field should contain an array of YAML-encoded references, for example:

```yaml
---
references:
- type: article-journal
  id: WatsonCrick1953
  author:
  - family: Watson
    given: J. D.
  - family: Crick
    given: F. H. C.
  issued:
    date-parts:
    - - 1953
      - 4
      - 25
  title: 'Molecular structure of nucleic acids: a structure for
    deoxyribose nucleic acid'
  title-short: Molecular structure of nucleic acids
  container-title: Nature
  volume: 171
  issue: 4356
  page: 737-738
  DOI: 10.1038/171737a0
  URL: https://www.nature.com/articles/171737a0
  language: en-GB
...
```

If both an external bibliography and inline (YAML metadata) references are provided, both will be used. In case of conflicting `id`s, the inline references will take precedence.

Note that pandoc can be used to produce such a YAML metadata section from a BibTeX, BibLaTeX, or CSL JSON bibliography:

```
pandoc chem.bib -s -f biblatex -t markdown
pandoc chem.json -s -f csljson -t markdown
```

Indeed, pandoc can convert between any of these citation formats:

```
pandoc chem.bib -s -f biblatex -t csljson
pandoc chem.yaml -s -f markdown -t biblatex
```

Running pandoc on a bibliography file with the `--citeproc` option will create a formatted bibliography in the format of your choice:

```
pandoc chem.bib -s --citeproc -o chem.html
pandoc chem.bib -s --citeproc -o chem.pdf
```

### 9.1.1 Capitalization in titles

If you are using a bibtex or biblatex bibliography, then observe the following rules:

- English titles should be in title case. Non-English titles should be in sentence case, and the `langid` field in biblatex should be set to the relevant language. (The following values are treated as English: `american`, `british`, `canadian`, `english`, `australian`, `newzealand`, `USenglish`, or `UKenglish`.)

- As is standard with bibtex/biblatex, proper names should be protected with curly braces so that they won't be lowercased in styles that call for sentence case. For example:

```
title = {My Dinner with {Andre}}
```

- In addition, words that should remain lowercase (or camelCase) should be protected:

```
title = {Spin Wave Dispersion on the {nm} Scale}
```

Though this is not necessary in bibtex/biblatex, it is necessary with citeproc, which stores titles internally in sentence case, and converts to title case in styles that require it. Here we protect "nm" so that it doesn't get converted to "Nm" at this stage.

If you are using a CSL bibliography (either JSON or YAML), then observe the following rules:

- All titles should be in sentence case.

- Use the `language` field for non-English titles to prevent their conversion to title case in styles that call for this. (Conversion happens only if `language` begins with `en` or is left empty.)

- Protect words that should not be converted to title case using this syntax:

```
Spin wave dispersion on the <span class="nocase">nm</span> scale
```

### 9.1.2 Conference papers, published vs. unpublished

For a formally published conference paper, use the biblatex entry type `inproceedings` (which will be mapped to CSL `paper-conference`).

For an unpublished manuscript, use the biblatex entry type `unpublished` without an `eventtitle` field (this entry type will be mapped to CSL `manuscript`).

For a talk, an unpublished conference paper, or a poster presentation, use the biblatex entry type `unpublished` with an `eventtitle` field (this entry type will be mapped to CSL `speech`). Use the biblatex `type` field to indicate the type, e.g. "Paper", or "Poster". `venue` and `eventdate` may be useful too, though `eventdate` will not be rendered by most CSL styles. Note that `venue` is for the event's venue, unlike `location` which describes the publisher's location; do not use the latter for an unpublished conference paper.

---

## 9.2 Specifying a citation style

Citations and references can be formatted using any style supported by the [Citation Style Language](https://citationstyles.org), with options listed in the [Zotero Style Repository](https://www.zotero.org/styles). Specify these files using the `--csl` option or the `csl` (or `citation-style`) metadata field.

By default, pandoc applies the Chicago Manual of Style author-date format. You can establish a different default by placing a CSL style file named `default.csl` in your user data directory. The CSL project offers guidance on [finding and editing styles](https://citationstyles.org/authors/).

### Citation abbreviations

The `--citation-abbreviations` option (or the `citation-abbreviations` metadata field) allows you to designate a JSON file containing journal abbreviations for use in formatted bibliographies when `form="short"` is specified.

Example format:

```json
{ "default": {
    "container-title": {
            "Lloyd's Law Reports": "Lloyd's Rep",
            "Estates Gazette": "EG",
            "Scots Law Times": "SLT"
    }
  }
}
```

---

## 9.3 Citations in note styles

Pandoc's citation processing enables switching between author-date, numerical, and note styles without changing the Markdown source. When using note styles, citations should be inserted like author-date style rather than manual footnotes. For example:

```
Blah blah [@foo, p. 33].
```

The footnote generates automatically. Pandoc manages spacing and note placement relative to punctuation based on the `notes-after-punctuation` setting (see Other relevant metadata fields section).

### Citations within footnotes

Sometimes citations must appear inside regular footnotes. Standard citations like `[@foo, p. 33]` render in parentheses within footnotes. In-text citations like `@foo [p. 33]` render without parentheses, with commas added as needed. Example:

```
[^1]:  Some studies [@foo; @bar, p. 33] show that
frubulicious zoosnaps are quantical.  For a survey
of the literature, see @baz [chap. 1].
```

---

## 9.4 Placement of the bibliography

If the style calls for a list of works cited, it will be placed in a div with id `refs`, if one exists:

```
::: {#refs}
:::
```

Otherwise, it will be placed at the end of the document. Generation of the bibliography can be suppressed by setting `suppress-bibliography: true` in the YAML metadata.

If you wish the bibliography to have a section heading, you can set `reference-section-title` in the metadata, or put the heading at the beginning of the div with id `refs` (if you are using it) or at the end of your document:

```
last paragraph...

# References
```

The bibliography will be inserted after this heading. Note that the `unnumbered` class will be added to this heading, so that the section will not be numbered.

If you want to put the bibliography into a variable in your template, one way to do that is to put the div with id `refs` into a metadata field, e.g.

```
---
refs: |
   ::: {#refs}
   :::
...
```

You can then put the variable `$refs$` into your template where you want the bibliography to be placed.

Note: if `--file-scope` is used, a div written this way will be given an identifier of the form `FILE__refs`, to avoid duplicate identifiers (see `--file-scope`). In view of this possibility, pandoc will place the bibliography in any div whose identifier is `refs` or ends with `__refs`.

---

## 9.5 Including uncited items in the bibliography

To include bibliography entries without citing them in the document body, define a `nocite` metadata field:

```
---
nocite: |
  @item1, @item2
...

@item3
```

In this example, only `item3` appears as a citation in the text, but the bibliography lists all three items.

To generate a bibliography containing all available citations regardless of whether they're referenced in the document, use a wildcard:

```
---
nocite: |
  @*
...
```

For LaTeX output, you can use [natbib](https://ctan.org/pkg/natbib) or [biblatex](https://ctan.org/pkg/biblatex) to render bibliographies. Specify bibliography files and add either `--natbib` or `--biblatex` to your pandoc command. Bibliography files have to be in either BibTeX (for `--natbib`) or BibLaTeX (for `--biblatex`) format.

---

## 9.6 Other relevant metadata fields

A few other metadata fields affect bibliography formatting:

### `link-citations`

If true, citations will be hyperlinked to the corresponding bibliography entries (for author-date and numerical styles only). Defaults to false.

### `link-bibliography`

If true, DOIs, PMCIDs, PMID, and URLs in bibliographies will be rendered as hyperlinks. (If an entry contains a DOI, PMCID, PMID, or URL, but none of these fields are rendered by the style, then the title, or in the absence of a title the whole entry, will be hyperlinked.) Defaults to true.

### `lang`

The `lang` field will affect how the style is localized, for example in the translation of labels, the use of quotation marks, and the way items are sorted. (For backwards compatibility, `locale` may be used instead of `lang`, but this use is deprecated.) A BCP 47 language tag is expected: for example, `en`, `de`, `en-US`, `fr-CA`, `ug-Cyrl`. The unicode extension syntax (after `-u-`) may be used to specify options for collation (sorting) more precisely. Here are some examples:

- `zh-u-co-pinyin`: Chinese with the Pinyin collation.
- `es-u-co-trad`: Spanish with the traditional collation (with `Ch` sorting after `C`).
- `fr-u-kb`: French with "backwards" accent sorting (with `cote` sorting after `cote`).
- `en-US-u-kf-upper`: English with uppercase letters sorting before lower (default is lower before upper).

### `notes-after-punctuation`

If true (the default for note styles), pandoc will put footnote references or superscripted numerical citations after following punctuation. For example, if the source contains `blah blah [@jones99].`, the result will look like `blah blah.[^1]`, with the note moved after the period and the space collapsed. If false, the space will still be collapsed, but the footnote will not be moved after the punctuation. The option may also be used in numerical styles that use superscripts for citation numbers (but for these styles the default is not to move the citation).
