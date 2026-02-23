# 11 EPUBs

---

## 11.1 EPUB metadata

There are two approaches to defining metadata for EPUB files. The first uses the `--epub-metadata` option with an XML file containing Dublin Core elements. The second leverages YAML, either embedded as a metadata block within Markdown or as a separate file via `--metadata-file`.

### YAML Metadata Example

```yaml
---
title:
- type: main
  text: My Book
- type: subtitle
  text: An investigation of metadata
creator:
- role: author
  text: John Smith
- role: editor
  text: Sarah Jones
identifier:
- scheme: DOI
  text: doi:10.234234.234/33
publisher:  My Press
rights: (c) 2007 John Smith, CC BY-NC
ibooks:
  version: 1.3.4
...
```

### Recognized Fields

**identifier**

Either a string or object with `text` and `scheme` fields. Valid schemes: ISBN-10, GTIN-13, UPC, ISMN-10, DOI, LCCN, GTIN-14, ISBN-13, Legal deposit number, URN, OCLC, ISMN-13, ISBN-A, JP, OLCC.

**title**

String, or object with `file-as` and `type` fields, or list. Valid types: main, subtitle, short, collection, edition, extended.

**creator**

String, or object with `role`, `file-as`, and `text` fields, or list. Role values follow MARC relators, with human-readable translations supported.

**contributor**

Same format as creator.

**date**

String in `YYYY-MM-DD` format. Year alone suffices; Pandoc converts common date formats.

**lang** (or legacy: **language**)

String in BCP 47 format. Defaults to local language if unspecified.

**subject**

String, or object with `text`, `authority`, and `term` fields, or list. Reserved authorities include AAT, BIC, BISAC, CLC, DDC, CLIL, EuroVoc, MEDTOP, LCSH, NDC, Thema, UDC, and WGS.

**description**

String value.

**type**

String value.

**format**

String value.

**relation**

String value.

**coverage**

String value.

**rights**

String value.

**belongs-to-collection**

String identifying the collection name.

**group-position**

Numeric position within the collection.

**cover-image**

String path to cover image.

**css** (or legacy: **stylesheet**)

String path to CSS stylesheet.

**page-progression-direction**

Either `ltr` or `rtl`. Sets the spine element attribute.

**accessModes**

Array of strings. Defaults to `["textual"]`.

**accessModeSufficient**

Array of strings. Defaults to `["textual"]`.

**accessibilityHazards**

Array of strings. Defaults to `["none"]`.

**accessibilityFeatures**

Array of strings. Defaults to:

- alternativeText
- readingOrder
- structuralNavigation
- tableOfContents

**accessibilitySummary**

String value.

**ibooks**

iBooks-specific metadata with fields:

- `version`: string
- `specified-fonts`: true|false (default false)
- `ipad-orientation-lock`: portrait-only|landscape-only
- `iphone-orientation-lock`: portrait-only|landscape-only
- `binding`: true|false (default true)
- `scroll-axis`: vertical|horizontal|default

---

## 11.2 The `epub:type` attribute

For `epub3` output, you can mark up the heading that corresponds to an EPUB chapter using the `epub:type` attribute. For example, to set the attribute to the value `prologue`, use this Markdown:

```
# My chapter {epub:type=prologue}
```

Which will result in:

```html
<body epub:type="frontmatter">
  <section epub:type="prologue">
    <h1>My chapter</h1>
```

Pandoc will output `<body epub:type="bodymatter">`, unless you use one of the following values, in which case either `frontmatter` or `backmatter` will be output.

| `epub:type` of first section | `epub:type` of body |
|-----|-----|
| prologue | frontmatter |
| abstract | frontmatter |
| copyright-page | frontmatter |
| dedication | frontmatter |
| credits | frontmatter |
| keywords | frontmatter |
| imprint | frontmatter |
| contributors | frontmatter |
| other-credits | frontmatter |
| errata | frontmatter |
| revision-history | frontmatter |
| titlepage | frontmatter |
| halftitlepage | frontmatter |
| seriespage | frontmatter |
| foreword | frontmatter |
| preface | frontmatter |
| frontispiece | frontmatter |
| appendix | backmatter |
| colophon | backmatter |
| bibliography | backmatter |
| index | backmatter |

---

## 11.3 Linked media

By default, pandoc automatically downloads media from `<img>`, `<audio>`, `<video>`, and `<source>` elements and includes them in the EPUB container, creating a self-contained package. To link to external media instead, use raw HTML with `data-external="1"` on the tag containing the `src` attribute.

### Example

```html
<audio controls="1">
  <source src="https://example.com/music/toccata.mp3"
          data-external="1" type="audio/mpeg">
  </source>
</audio>
```

### Implementation Notes

- For HTML input format, `data-external="1"` works as expected with `<img>` elements
- In Markdown, external images use the syntax: `![img](url){external=1}`
- The external flag only applies to images; other media elements lack native AST representation and require raw HTML

---

## 11.4 EPUB styling

By default, pandoc includes basic styling from its `epub.css` data file. Access this file using `pandoc --print-default-data-file epub.css`. To apply custom CSS, use the `--css` command line option.

The tool adds some inline styles beyond the default stylesheet. These inline definitions are essential for correct formatting of pandoc's HTML output.

The `document-css` variable enables more opinionated styling of pandoc's default HTML templates if desired. When activated, you may leverage options described in Variables for HTML to customize the appearance further.
