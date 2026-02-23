# 6 Templates

When the `-s/--standalone` option is used, pandoc employs a template to incorporate header and footer content necessary for self-contained documents. To view the default template for your output format, execute:

```
pandoc -D FORMAT
```

Replace `FORMAT` with your desired output format name. A custom template can be applied using the `--template` option. System default templates for a given output format can be overridden by placing a file named `templates/default.FORMAT` in the user data directory (see `--data-dir`).

### Exceptions

- **ODT output**: customize the `default.opendocument` template
- **DOCX output**: customize the `default.openxml` template
- **PDF output**: customize the `default.latex` template (or `default.context` if using `-t context`, or `default.ms` if using `-t ms`, or `default.html` if using `-t html`)
- **PPTX**: has no template

Note that `docx`, `odt`, and `pptx` output formats support additional customization via `--reference-doc`. Reference documents adjust document styles; templates handle variable interpolation and customize metadata presentation, table of contents positioning, and boilerplate text.

### Variables

Templates contain variables enabling arbitrary information insertion. These can be set via the `-V/--variable` command-line option. When a variable is undefined, pandoc checks the document's metadata (configured through YAML metadata blocks or the `-M/--metadata` option). Pandoc assigns default values to certain variables -- see the Variables section below for details on default template variables.

When using custom templates, revisions may be necessary as pandoc evolves. Track default template changes and update custom templates accordingly. The [pandoc-templates](https://github.com/jgm/pandoc-templates) repository can be forked for easy change management.

---

## 6.1 Template syntax

### 6.1.1 Comments

Content between `$--` and the end of a line functions as a comment and gets excluded from output.

### 6.1.2 Delimiters

Templates use either `$`...`$` or `${`...`}` as delimiters for variables and control structures. Styles may be mixed, but opening and closing delimiters must match. The opening delimiter may be followed by spaces or tabs (ignored), and the closing delimiter may be preceded by spaces or tabs (ignored).

To include a literal `$`, use `$$`.

### 6.1.3 Interpolated variables

Variables are marked with matched delimiters. Names must start with a letter and contain letters, numbers, `_`, `-`, and `.`. Reserved keywords (`it`, `if`, `else`, `endif`, `for`, `sep`, `endfor`) cannot be variable names.

Examples:

```
$foo$
$foo.bar.baz$
$foo_bar.baz-bim$
$ foo $
${foo}
${foo.bar.baz}
${foo_bar.baz-bim}
${ foo }
```

Period-separated names access structured values. Rendering behavior:

- Simple values render verbatim (unescaped)
- Lists concatenate their values
- Maps render as `true`
- All other values render as empty string

### 6.1.4 Conditionals

Conditionals begin with `if(variable)` and end with `endif`, optionally containing `else`. The `if` section executes for true variables; `else` executes otherwise.

True values include:

- Any map
- Arrays containing at least one true value
- Any nonempty string
- Boolean True

Note: YAML metadata and `-M/--metadata` interpret unquoted `true`/`false` as Booleans. The `-V/--variable` flag always produces string values.

Examples:

```
$if(foo)$bar$endif$

$if(foo)$
  $foo$
$endif$

$if(foo)$
part one
$else$
part two
$endif$

${if(foo)}bar${endif}

${if(foo)}
  ${foo}
${endif}

${if(foo)}
${ foo.bar }
${else}
no foo!
${endif}
```

The `elseif` keyword simplifies nested conditionals:

```
$if(foo)$
XXX
$elseif(bar)$
YYY
$else$
ZZZ
$endif$
```

### 6.1.5 For loops

For loops begin with `for(variable)` and end with `endfor`.

- Arrays: material repeats with the variable set to each array value
- Maps: material sets to the map
- Other values: single iteration performed

Examples:

```
$for(foo)$$foo$$sep$, $endfor$

$for(foo)$
  - $foo.last$, $foo.first$
$endfor$

${ for(foo.bar) }
  - ${ foo.bar.last }, ${ foo.bar.first }
${ endfor }

$for(mymap)$
$it.name$: $it.office$
$endfor$
```

Separators between consecutive values use `sep`:

```
${ for(foo) }${ foo }${ sep }, ${ endfor }
```

The anaphoric keyword `it` can replace the variable inside loops:

```
${ for(foo.bar) }
  - ${ it.last }, ${ it.first }
${ endfor }
```

### 6.1.6 Partials

Subtemplates in separate files get included using the partial name followed by `()`:

```
${ styles() }
```

Partials are sought in the template's directory, with the same extension assumed. Full names with extensions work:

```
${ styles.html() }
```

If not found and the template uses a relative path, the `templates` subdirectory of the user data directory is checked.

Partials apply to variables using a colon:

```
${ date:fancy() }

${ articles:bibentry() }
```

When `articles` is an array, the partial applies to each value. The anaphoric `it` keyword must be used in partials when iterating.

Final newlines from included partials are omitted.

Partials may nest other partials.

Separators for array values use square brackets:

```
${months[, ]}

${articles:bibentry()[; ]}
```

The separator is literal and cannot contain interpolated variables or directives.

### 6.1.7 Nesting

The `^` directive ensures content nests with proper indentation:

```
$item.number$  $^$$item.description$ ($item.price$)
```

Result when `item.description` spans multiple lines:

```
00123  A fine bottle of 18-year old
       Oban whiskey. ($148)
```

Multiple lines nest to the same level by aligning with the `^` directive:

```
$item.number$  $^$$item.description$ ($item.price$)
               (Available til $item.sellby$.)
```

Result:

```
00123  A fine bottle of 18-year old
       Oban whiskey. ($148)
       (Available til March 30, 2020.)
```

Variables alone on lines with preceding whitespace automatically nest when their values contain multiple lines.

### 6.1.8 Breakable spaces

Template spaces normally don't break, but the `~` keyword creates breakable regions:

```
$~$This long line may break if the document is rendered
with a short line length.$~$
```

### 6.1.9 Pipes

Pipes transform variable or partial values using a slash (`/`) between the name and pipe name:

```
$for(name)$
$name/uppercase$
$endfor$

$for(metadata/pairs)$
- $it.key$: $it.value$
$endfor$

$employee:name()/uppercase$
```

Pipes chain together:

```
$for(employees/pairs)$
$it.key/alpha/uppercase$. $it.name$
$endfor$
```

Some pipes accept parameters:

```
|----------------------|------------|
$for(employee)$
$it.name.first/uppercase/left 20 "| "$$it.name.salary/right 10 " | " " |"$
$endfor$
|----------------------|------------|
```

#### Predefined pipes

- **`pairs`**: Converts maps or arrays to arrays with `key` and `value` fields. Array indices start at 1.
- **`uppercase`**: Converts text to uppercase.
- **`lowercase`**: Converts text to lowercase.
- **`length`**: Returns character count for text, element count for maps/arrays.
- **`reverse`**: Reverses text or arrays; no effect elsewhere.
- **`first`**: Returns first array value, or original value if array is empty.
- **`last`**: Returns last array value, or original value if array is empty.
- **`rest`**: Returns all but first array value, or original value if array is empty.
- **`allbutlast`**: Returns all but last array value, or original value if array is empty.
- **`chomp`**: Removes trailing newlines and breakable space.
- **`nowrap`**: Disables line wrapping on breakable spaces.
- **`alpha`**: Converts integer-readable text to lowercase letters `a..z` (mod 26). Chain with `uppercase` for capitals.
- **`roman`**: Converts integer-readable text to lowercase roman numerals. Chain with `uppercase` for capitals.
- **`left n "leftborder" "rightborder"`**: Left-aligns text in width-`n` block with optional borders. Affects only text values.
- **`right n "leftborder" "rightborder"`**: Right-aligns text in width-`n` block with optional borders.
- **`center n "leftborder" "rightborder"`**: Center-aligns text in width-`n` block with optional borders.

---

## 6.2 Variables

### 6.2.1 Metadata variables

`title`, `author`, `date`

These fields allow identification of basic aspects of the document. Included in PDF metadata through LaTeX and ConTeXt. They can be configured via pandoc title blocks or YAML metadata blocks supporting multiple authors.

Additional metadata variables include:

- `title-meta`, `author-meta`, `date-meta` -- for setting PDF/HTML metadata without including title blocks in the document
- `pagetitle` -- sets the HTML page title (defaults to `title`)
- `subtitle` -- document subtitle for HTML, EPUB, LaTeX, ConTeXt, and docx
- `abstract` -- document summary for HTML, LaTeX, ConTeXt, AsciiDoc, and docx
- `abstract-title` -- title of abstract (HTML, EPUB, docx, Typst; auto-localized by default)
- `keywords` -- list for HTML, PDF, ODT, pptx, docx, AsciiDoc metadata
- `subject` -- for ODT, PDF, docx, EPUB, pptx metadata
- `description` -- for ODT, docx, pptx metadata (may display as Comments)
- `category` -- for docx and pptx metadata

Any root-level string metadata not included in standard properties is added as a custom property when converting to docx, ODT, or pptx.

### 6.2.2 Language variables

**`lang`**

Identifies the main language using IETF language tags following BCP 47 standard (e.g., `en` or `en-GB`). This affects most formats and controls hyphenation in PDF output using LaTeX or ConTeXt. Native pandoc Divs and Spans can include the `lang` attribute to switch language within documents.

**`dir`**

The base script direction: either `rtl` (right-to-left) or `ltr` (left-to-right). For bidirectional documents, native pandoc spans and divs with the `dir` attribute can override the base direction in some output formats. When using LaTeX, only the `xelatex` engine fully supports bidirectional documents.

### 6.2.3 Variables for HTML

**`document-css`**

Enables inclusion of most CSS from the `styles.html` partial. Unless you use `--css`, this variable is set to `true` by default. Disable with `-M document-css=false`.

- `mainfont` -- sets CSS `font-family` on the `html` element
- `fontsize` -- sets base CSS `font-size` (e.g., `20px` or `12pt`)
- `fontcolor` -- sets CSS `color` property on `html` element
- `linkcolor` -- sets CSS `color` on all links
- `monofont` -- sets CSS `font-family` on `code` elements
- `monobackgroundcolor` -- sets CSS `background-color` on `code` elements with extra padding
- `linestretch` -- sets CSS `line-height` (unitless preferred)
- `maxwidth` -- sets CSS `max-width` (default is 36em)
- `backgroundcolor` -- sets CSS `background-color` on `html` element
- `margin-left`, `margin-right`, `margin-top`, `margin-bottom` -- set corresponding CSS `padding` on `body` element

To override CSS for one document, include custom styles in metadata:

```yaml
---
header-includes: |
  <style>
  blockquote {
    font-style: italic;
  }
  tr.even {
    background-color: #f0f0f0;
  }
  td, th {
    padding: 0.5em 2em 0.5em 0.5em;
  }
  tbody {
    border-bottom: none;
  }
  </style>
---
```

### 6.2.4 Variables for HTML math

**`classoption`**

When using `--katex`, render display math equations flush left with YAML metadata or `-M classoption=fleqn`.

### 6.2.5 Variables for HTML slides

These variables affect HTML slide show output.

- `institute` -- author affiliations (can be a list for multiple authors)
- `revealjs-url` -- base URL for reveal.js documents (defaults to `https://unpkg.com/reveal.js@^5`)
- `s5-url` -- base URL for S5 documents (defaults to `s5/default`)
- `slidy-url` -- base URL for Slidy documents (defaults to `https://www.w3.org/Talks/Tools/Slidy2`)
- `slideous-url` -- base URL for Slideous documents (defaults to `slideous`)
- `title-slide-attributes` -- additional attributes for reveal.js title slides
- `highlightjs-theme` -- highlight.js theme for code highlighting with `--syntax-highlighting=idiomatic` (defaults to `monokai`)

All reveal.js configuration options are available as variables. Use `0` to disable boolean flags that default to true.

### 6.2.6 Variables for Beamer slides

These variables change the appearance of PDF slides using beamer.

- `aspectratio` -- slide aspect ratio: `43` (4:3, default), `169` (16:9), `1610` (16:10), `149` (14:9), `141` (1.41:1), `54` (5:4), `32` (3:2)
- `beameroption` -- add extra beamer option with `\setbeameroption{}`
- `institute` -- author affiliations (list for multiple authors)
- `logo` -- logo image for slides
- `navigation` -- controls navigation symbols (`empty` for none; valid: `frame`, `vertical`, `horizontal`)
- `section-titles` -- enables title pages for new sections (default is true)
- `theme`, `colortheme`, `fonttheme`, `innertheme`, `outertheme` -- beamer themes
- `themeoptions`, `colorthemeoptions`, `fontthemeoptions`, `innerthemeoptions`, `outerthemeoptions` -- options for LaTeX beamer themes (lists)
- `titlegraphic` -- image for title slide (can be a list)
- `titlegraphicoptions` -- options for title slide image
- `shorttitle`, `shortsubtitle`, `shortauthor`, `shortinstitute`, `shortdate` -- short versions used by some beamer themes

### 6.2.7 Variables for PowerPoint

- `monofont` -- font to use for code

### 6.2.8 Variables for LaTeX

Pandoc uses these variables when creating PDFs with a LaTeX engine.

#### 6.2.8.1 Layout

- `block-headings` -- make `\paragraph` and `\subparagraph` (fourth- and fifth-level headings) free-standing rather than run-in; requires further formatting to distinguish from `\subsubsection`. Alternatively, use KOMA-Script to adjust headings more extensively:

```yaml
---
documentclass: scrartcl
header-includes: |
  \RedeclareSectionCommand[
    beforeskip=-10pt plus -2pt minus -1pt,
    afterskip=1sp plus -1sp minus 1sp,
    font=\normalfont\itshape]{paragraph}
  \RedeclareSectionCommand[
    beforeskip=-10pt plus -2pt minus -1pt,
    afterskip=1sp plus -1sp minus 1sp,
    font=\normalfont\scshape,
    indent=0pt]{subparagraph}
...
```

- `classoption` -- option for document class (e.g., `oneside`); repeat for multiple:

```yaml
---
classoption:
- twocolumn
- landscape
...
```

- `documentclass` -- document class: standard (`article`, `book`, `report`), KOMA-Script (`scrartcl`, `scrbook`, `scrreprt`), or `memoir`
- `geometry` -- option for geometry package (e.g., `margin=1in`); repeat for multiple:

```yaml
---
geometry:
- top=30mm
- left=20mm
- heightrounded
...
```

- `shorthands` -- enable language-specific shorthands when loading babel (by default, pandoc includes `shorthands=off`)
- `hyperrefoptions` -- option for hyperref package (e.g., `linktoc=all`); repeat for multiple:

```yaml
---
hyperrefoptions:
- linktoc=all
- pdfwindowui
- pdfpagemode=FullScreen
...
```

- `indent` -- if true, use document class settings for indentation (default LaTeX template removes indentation and adds space between paragraphs)
- `linestretch` -- adjusts line spacing using setspace package (e.g., `1.25`, `1.5`)
- `margin-left`, `margin-right`, `margin-top`, `margin-bottom` -- sets margins if geometry is not used
- `pagestyle` -- control `\pagestyle{}`: article class supports `plain` (default), `empty`, `headings`
- `papersize` -- paper size (e.g., `letter`, `a4`)
- `secnumdepth` -- numbering depth for sections (with `--number-sections` or `numbersections` variable)
- `beamerarticle` -- produce an article from Beamer slides; use with beamer writer but default LaTeX template
- `handout` -- produce handout version of Beamer slides with overlays condensed
- `csquotes` -- load csquotes package and use `\enquote` or `\enquote*` for quoted text
- `csquotesoptions` -- options for csquotes package (repeat for multiple)
- `babeloptions` -- options to pass to babel package (may be repeated); defaults to `provide=*` if main language isn't European Latin/Cyrillic or Vietnamese

#### 6.2.8.2 Fonts

- `fontenc` -- font encoding via fontenc package (with pdflatex); default is `T1`
- `fontfamily` -- font package for pdflatex; default is Latin Modern
- `fontfamilyoptions` -- options for fontfamily package; repeat for multiple. Example using Libertine:

```yaml
---
fontfamily: libertinus
fontfamilyoptions:
- osf
- p
...
```

- `fontsize` -- font size for body text (10pt, 11pt, 12pt standard; use KOMA-Script for other sizes)
- `mainfont`, `sansfont`, `monofont`, `mathfont`, `CJKmainfont`, `CJKsansfont`, `CJKmonofont` -- font families for xelatex/lualatex using fontspec package; CJK fonts use xecjk (xelatex) or luatexja (lualatex)
- `mainfontoptions`, `sansfontoptions`, `monofontoptions`, `mathfontoptions`, `CJKoptions`, `luatexjapresetoptions` -- options for fonts in xelatex/lualatex via fontspec; repeat for multiple. Example with TeX Gyre Pagella:

```yaml
---
mainfont: TeX Gyre Pagella
mainfontoptions:
- Numbers=Lowercase
- Numbers=Proportional
...
```

- `mainfontfallback`, `sansfontfallback`, `monofontfallback` -- fonts to try if glyph not found; are lists with font names followed by colon and optional options:

```yaml
---
mainfontfallback:
  - "FreeSans:"
  - "NotoColorEmoji:mode=harf"
...
```

Font fallbacks work only with lualatex.

- `babelfonts` -- map Babel language names to fonts:

```yaml
---
babelfonts:
  chinese-hant: "Noto Serif CJK TC"
  russian: "Noto Serif"
...
```

- `microtypeoptions` -- options to pass to microtype package

#### 6.2.8.3 Links

- `colorlinks` -- add color to link text; automatically enabled if any of `linkcolor`, `filecolor`, `citecolor`, `urlcolor`, or `toccolor` are set
- `boxlinks` -- add visible box around links (no effect if `colorlinks` is set)
- `linkcolor`, `filecolor`, `citecolor`, `urlcolor`, `toccolor` -- colors for internal links, external links, citation links, linked URLs, and table of contents links using xcolor options (dvipsnames, svgnames, x11names)
- `links-as-notes` -- causes links to be printed as footnotes
- `urlstyle` -- style for URLs (e.g., `tt`, `rm`, `sf`; default is `same`)

#### 6.2.8.4 Front matter

- `lof`, `lot` -- include list of figures and list of tables (also via `--lof/--list-of-figures`, `--lot/--list-of-tables`)
- `thanks` -- contents of acknowledgments footnote after document title
- `toc` -- include table of contents (also via `--toc/--table-of-contents`)
- `toc-depth` -- level of section to include in table of contents

#### 6.2.8.5 BibLaTeX Bibliographies

These variables work when using BibLaTeX for citation rendering.

- `biblatexoptions` -- list of options for biblatex
- `biblio-style` -- bibliography style with `--natbib` and `--biblatex`
- `biblio-title` -- bibliography title with `--natbib` and `--biblatex`
- `bibliography` -- bibliography to use for resolving references
- `natbiboptions` -- list of options for natbib

#### 6.2.8.6 Other

- `pdf-trailer-id` -- PDF trailer ID; must be two PDF byte strings (conventionally 16 bytes each):

```
<00112233445566778899aabbccddeeff> <00112233445566778899aabbccddeeff>
```

- `pdfstandard` -- PDF standard(s) for document (e.g., `ua-2`, `a-4f`); supports PDF/A, PDF/X, PDF/UA variants; requires LuaLaTeX and LaTeX 2023+; repeat for multiple:

```yaml
---
pdfstandard:
- ua-2
- a-4f
...
```

### 6.2.9 Variables for ConTeXt

Pandoc uses these variables when creating PDFs with ConTeXt.

- `fontsize` -- font size for body text (e.g., `10pt`, `12pt`)
- `headertext`, `footertext` -- text in running header or footer; repeat up to four times for different placement
- `indenting` -- controls paragraph indentation (e.g., `yes,small,next`); repeat for multiple options
- `interlinespace` -- adjusts line spacing (e.g., `4ex`); repeat for multiple options
- `layout` -- options for page margins and text arrangement; repeat for multiple options
- `linkcolor`, `contrastcolor` -- colors for links outside and inside a page (e.g., `red`, `blue`)
- `linkstyle` -- typeface style for links (e.g., `normal`, `bold`, `slanted`, `boldslanted`, `type`, `cap`, `small`)
- `lof`, `lot` -- include list of figures and list of tables
- `mainfont`, `sansfont`, `monofont`, `mathfont` -- font families (any system font name)
- `mainfontfallback`, `sansfontfallback`, `monofontfallback` -- list of fallback fonts; use `\definefallbackfamily`-compatible syntax; emoji fonts unsupported
- `margin-left`, `margin-right`, `margin-top`, `margin-bottom` -- sets margins if layout is not used
- `pagenumbering` -- page number style and location; repeat for multiple options
- `papersize` -- paper size (e.g., `letter`, `A4`, `landscape`); repeat for multiple options
- `pdfa` -- adds setup for PDF/A type (e.g., `1a:2005`, `2a`); defaults to `1b:2005` if value is true; requires ICC color profiles and standard-conforming content
- `pdfaiccprofile` -- ICC profile with `pdfa` (e.g., `default.cmyk`); defaults to `sRGB.icc`; may be repeated
- `pdfaintent` -- output intent with `pdfa` (e.g., `ISO coated v2 300% (ECI)`); defaults to `sRGB IEC61966-2.1`
- `toc` -- include table of contents (also via `--toc/--table-of-contents`)
- `urlstyle` -- typeface style for URLs without link text (e.g., `normal`, `bold`, `slanted`, `boldslanted`, `type`, `cap`, `small`)
- `whitespace` -- spacing between paragraphs (e.g., `none`, `small`)
- `includesource` -- include all source documents as file attachments in PDF

### 6.2.10 Variables for wkhtmltopdf

Pandoc uses these when creating PDFs with wkhtmltopdf. The `--css` option also affects output.

- `footer-html`, `header-html` -- add information to header and footer
- `margin-left`, `margin-right`, `margin-top`, `margin-bottom` -- set page margins
- `papersize` -- sets PDF paper size

### 6.2.11 Variables for man pages

- `adjusting` -- adjusts text to left (`l`), right (`r`), center (`c`), or both (`b`) margins
- `footer` -- footer in man pages
- `header` -- header in man pages
- `section` -- section number in man pages

### 6.2.12 Variables for Texinfo

- `version` -- version of software (used in title and title page)
- `filename` -- name of info file to generate (defaults to name based on texi filename)

### 6.2.13 Variables for Typst

- `template` -- Typst template to use (relative path only)
- `margin` -- dictionary with Typst fields: `x`, `y`, `top`, `bottom`, `left`, `right`
- `papersize` -- paper size: `a4`, `us-letter`, etc.
- `mainfont` -- system font name for main font
- `fontsize` -- font size (e.g., `12pt`)
- `section-numbering` -- schema for numbering sections (e.g., `1.A.1`)
- `page-numbering` -- schema for numbering pages (e.g., `1`, `i`, or empty string to omit)
- `columns` -- number of columns for body text
- `thanks` -- contents of acknowledgments footnote after document title
- `mathfont`, `codefont` -- system font names for math and code
- `linestretch` -- adjusts line spacing (e.g., `1.25`, `1.5`)
- `linkcolor`, `filecolor`, `citecolor` -- colors for external links, internal links, and citation links (hexadecimal codes)

### 6.2.14 Variables for ms

- `fontfamily` -- `A` (Avant Garde), `B` (Bookman), `C` (Helvetica), `HN` (Helvetica Narrow), `P` (Palatino), or `T` (Times New Roman); does not affect source code (always monospace Courier); built-in fonts have limited character coverage; additional fonts may be installed via script
- `indent` -- paragraph indent (e.g., `2m`)
- `lineheight` -- line height (e.g., `12p`)
- `pointsize` -- point size (e.g., `10p`)

### 6.2.15 Variables set automatically

Pandoc sets these automatically in response to options or document contents; users can modify them. These vary by output format.

- `body` -- body of document
- `date-meta` -- `date` variable converted to ISO 8601 YYYY-MM-DD for HTML-based formats. Recognized date formats: `mm/dd/yyyy`, `mm/dd/yy`, `yyyy-mm-dd`, `dd MM yyyy`, `MM dd, yyyy`, `yyyy[mm[dd]]`
- `header-includes` -- contents from `-H/--include-in-header` (multiple values)
- `include-before` -- contents from `-B/--include-before-body` (multiple values)
- `include-after` -- contents from `-A/--include-after-body` (multiple values)
- `meta-json` -- JSON representation of all document metadata; field values transformed to selected output format
- `numbersections` -- non-null if `-N/--number-sections` specified
- `sourcefile`, `outputfile` -- source and destination filenames. `sourcefile` can be a list for multiple inputs or empty for stdin; `outputfile` can be `-` for terminal output. Use template snippet to distinguish:

```
$if(sourcefile)$
$for(sourcefile)$
$sourcefile$
$endfor$
$else$
(stdin)
$endif$
```

For absolute paths, use `$curdir$/$sourcefile$`.

- `pdf-engine` -- name of PDF engine from `--pdf-engine` or default for format if PDF output requested
- `curdir` -- working directory from which pandoc is run
- `pandoc-version` -- pandoc version
- `toc` -- non-null if `--toc/--table-of-contents` specified
- `toc-title` -- title of table of contents (works with EPUB, HTML, revealjs, opendocument, odt, docx, pptx, beamer, LaTeX); in docx and pptx, picked from metadata but cannot be set as variable
