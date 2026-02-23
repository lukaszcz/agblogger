# 7 Extensions

The behavior of readers and writers can be adjusted by enabling or disabling various extensions.

Extensions are toggled by adding `+EXTENSION` or `-EXTENSION` to format names. For example:

- `--from markdown_strict+footnotes` enables footnotes in strict Markdown
- `--from markdown-footnotes-pipe_tables` disables footnotes and pipe tables in pandoc's Markdown

The Markdown reader and writer utilize extensions most extensively. Extensions specific to Markdown are documented in the Pandoc's Markdown section, with variants covered under Markdown variants for `commonmark` and `gfm`.

The following section addresses extensions that work across multiple formats.

Markdown extensions added to the `ipynb` format affect Markdown cells in Jupyter notebooks (as do command-line options like `--markdown-headings`).

## 7.1 Typography

### 7.1.1 Extension: `smart`

Interpret straight quotes as curly quotes, `---` as em-dashes, `--` as en-dashes, and `...` as ellipses. Nonbreaking spaces are inserted after certain abbreviations, such as "Mr."

This extension can be enabled/disabled for the following formats:

**Input formats:**
`markdown`, `commonmark`, `latex`, `mediawiki`, `org`, `rst`, `twiki`, `html`

**Output formats:**
`markdown`, `latex`, `context`, `org`, `rst`

**Enabled by default in:**
`markdown`, `latex`, `context` (both input and output)

If you are *writing* Markdown, then the `smart` extension has the reverse effect: what would have been curly quotes comes out straight.

In LaTeX, `smart` means to use standard TeX ligatures for quotation marks (` `` ` and `''` for double quotes, `` ` `` and `'` for single quotes) and dashes (`--` for en-dash and `---` for em-dash). If `smart` is disabled, pandoc parses these characters literally when reading LaTeX. When writing LaTeX, enabling `smart` tells pandoc to use ligatures when possible; disabling it causes pandoc to use unicode quotation mark and dash characters.

## 7.2 Headings and sections

### 7.2.1 Extension: `auto_identifiers`

A heading without an explicitly specified identifier will be automatically assigned a unique identifier based on the heading text.

This extension can be enabled/disabled for the following formats:

**Input formats:** `markdown`, `latex`, `rst`, `mediawiki`, `textile`

**Output formats:** `markdown`, `muse`

**Enabled by default in:** `markdown`, `muse`

The default algorithm used to derive the identifier from the heading text is:

- Remove all formatting, links, etc.
- Remove all footnotes.
- Remove all non-alphanumeric characters, except underscores, hyphens, and periods.
- Replace all spaces and newlines with hyphens.
- Convert all alphabetic characters to lowercase.
- Remove everything up to the first letter (identifiers may not begin with a number or punctuation mark).
- If nothing is left after this, use the identifier `section`.

| Heading | Identifier |
|---------|-----------|
| `Heading identifiers in HTML` | `heading-identifiers-in-html` |
| `Maitre d'hotel` | `maitre-dhotel` |
| `*Dogs*?--in *my* house?` | `dogs--in-my-house` |
| `[HTML], [S5], or [RTF]?` | `html-s5-or-rtf` |
| `3. Applications` | `applications` |
| `33` | `section` |

When several headings have identical text, the first receives the standard identifier; subsequent ones append `-1`, `-2`, etc.

These identifiers provide link targets for table of contents and enable cross-document linking:

```
See the section on
[heading identifiers](#heading-identifiers-in-html-latex-and-context).
```

With the `--section-divs` option, each section is wrapped in a `<section>` or `<div>` tag, with the identifier attached to the enclosing element rather than the heading itself.

### 7.2.2 Extension: `ascii_identifiers`

This option causes the identifiers produced by `auto_identifiers` to be pure ASCII. Accents are stripped off of accented Latin letters, and non-Latin letters are omitted.

### 7.2.3 Extension: `gfm_auto_identifiers`

This modifies the algorithm to match GitHub's approach: spaces convert to dashes, uppercase converts to lowercase, punctuation (except `-` and `_`) is removed, and emojis are replaced by their names.

## 7.3 Math Input

The extensions `tex_math_dollars`, `tex_math_gfm`, `tex_math_single_backslash`, and `tex_math_double_backslash` are detailed in the section covering Pandoc's Markdown functionality.

These extensions function with HTML input as well. This capability proves beneficial when processing web pages that utilize MathJax formatting.

## 7.4 Raw HTML/TeX

The following extensions are described in more detail in their respective sections of Pandoc's Markdown:

- **`raw_html`** -- allows HTML elements which are not representable in pandoc's AST to be parsed as raw HTML. This is disabled by default for HTML input.

- **`raw_tex`** -- allows raw LaTeX, TeX, and ConTeXt to be included in a document. This extension can be enabled/disabled for:

  **Input formats:** `latex`, `textile`, `html` (environments, `\ref`, and `\eqref` only), `ipynb`

  **Output formats:** `textile`, `commonmark`

  When applied to `ipynb`, both `raw_html` and `raw_tex` affect not only raw TeX in Markdown cells, but also data with mime type `text/html` in output cells. For best results when converting to formats like `docx` that don't support raw HTML or TeX, disable these extensions.

- **`native_divs`** -- causes HTML `div` elements to be parsed as native pandoc Div blocks. To parse them as raw HTML instead, use `-f html-native_divs+raw_html`.

- **`native_spans`** -- causes HTML `span` elements to be parsed as native pandoc Span inlines. To parse them as raw HTML, use `-f html-native_spans+raw_html`. To drop all `div`s and `span`s when converting HTML to Markdown, use `pandoc -f html-native_divs-native_spans -t markdown`.

## 7.5 Literate Haskell support

### 7.5.1 Extension: `literate_haskell`

Treat the document as literate Haskell source.

This extension can be enabled/disabled for the following formats:

**Input formats:** `markdown`, `rst`, `latex`

**Output formats:** `markdown`, `rst`, `latex`, `html`

If you append `+lhs` (or `+literate_haskell`) to one of the formats above, pandoc will treat the document as literate Haskell source. This means that:

- In Markdown input, "bird track" sections will be parsed as Haskell code rather than block quotations. Text between `\begin{code}` and `\end{code}` will also be treated as Haskell code. For ATX-style headings the character `=` will be used instead of `#`.

- In Markdown output, code blocks with classes `haskell` and `literate` will be rendered using bird tracks, and block quotations will be indented one space, so they will not be treated as Haskell code. In addition, headings will be rendered setext-style (with underlines) rather than ATX-style (with `#` characters). (This is because ghc treats `#` characters in column 1 as introducing line numbers.)

- In restructured text input, "bird track" sections will be parsed as Haskell code.

- In restructured text output, code blocks with class `haskell` will be rendered using bird tracks.

- In LaTeX input, text in `code` environments will be parsed as Haskell code.

- In LaTeX output, code blocks with class `haskell` will be rendered inside `code` environments.

- In HTML output, code blocks with class `haskell` will be rendered with class `literatehaskell` and bird tracks.

Examples:

```
pandoc -f markdown+lhs -t html
```

reads literate Haskell source formatted with Markdown conventions and writes ordinary HTML (without bird tracks).

```
pandoc -f markdown+lhs -t html+lhs
```

writes HTML with the Haskell code in bird tracks, so it can be copied and pasted as literate Haskell source.

Note that GHC expects the bird tracks in the first column, so indented literate code blocks (e.g. inside an itemized environment) will not be picked up by the Haskell compiler.

## 7.6 Other extensions

### 7.6.1 Extension: `empty_paragraphs`

Permits empty paragraphs. By default, empty paragraphs are excluded.

**Input formats:** `docx`, `html`

**Output formats:** `docx`, `odt`, `opendocument`, `html`, `latex`

### 7.6.2 Extension: `native_numbering`

Activates native numbering for figures and tables, beginning at 1.

**Output formats:** `odt`, `opendocument`, `docx`

### 7.6.3 Extension: `xrefs_name`

Converts internal document links to cross-references displaying the referenced item's name or caption. Original link text is replaced upon document refresh. Works with `xrefs_number` to show numbers before names.

**Output formats:** `odt`, `opendocument`

### 7.6.4 Extension: `xrefs_number`

Transforms internal document links into cross-references using item numbers. Original link text is discarded. Requires heading numbers and caption display enabled for effectiveness. Works with `xrefs_name`.

**Output formats:** `odt`, `opendocument`

### 7.6.5 Extension: `styles`

During docx conversion, adds `custom-styles` attributes for all styles regardless of pandoc comprehension. Paragraph styles will cause Divs to be created and character styles will cause Spans to be created.

**Input formats:** `docx`

### 7.6.6 Extension: `amuse`

Enables Text::Amuse extensions to Emacs Muse markup in `muse` input format.

### 7.6.7 Extension: `raw_markdown`

In `ipynb` input, includes Markdown cells as raw blocks for lossless round-tripping instead of parsing.

### 7.6.8 Extension: `citations` (typst)

When enabled (default), typst citations parse as native pandoc citations, and vice versa.

### 7.6.9 Extension: `citations` (org)

Parses org-cite and org-ref citations as native pandoc citations; renders native pandoc citations as org-cite.

### 7.6.10 Extension: `citations` (docx)

Parses bibliographic plugin citations (Zotero, Mendeley, EndNote) as native pandoc citations.

### 7.6.11 Extension: `fancy_lists` (org)

Accepts aspects of Pandoc's Markdown fancy lists in org input, permitting lowercase and uppercase alphabetical markers for ordered lists.

### 7.6.12 Extension: `element_citations`

In `jats` output, replaces reference items with `<element-citation>` elements unaffected by CSL styles.

### 7.6.13 Extension: `ntb`

In `context` output, enables Natural Tables instead of default Extreme Tables for improved customization.

### 7.6.14 Extension: `smart_quotes` (org)

Interprets straight quotes as curly quotes during parsing. Reverses effect when writing Org. Implied when `smart` is enabled.

### 7.6.15 Extension: `special_strings` (org)

Interprets `---` as em-dashes, `--` as en-dashes, `\-` as shy hyphen, `...` as ellipses. Implied when `smart` is enabled.

### 7.6.16 Extension: `tagging`

With `context` output, generates tagged PDF markup with paragraph markers and alternative emphasis markup. Sets `emphasis-command` template variable.
