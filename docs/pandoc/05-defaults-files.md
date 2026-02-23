# 5 Defaults files

The `--defaults` option allows you to specify a package of options in a YAML or JSON file format.

## Basic Structure

Fields that are omitted retain their regular default values, allowing for minimal defaults files:

```yaml
verbosity: INFO
```

Or in JSON:

```json
{ "verbosity": "INFO" }
```

## Environment Variable Interpolation

In fields expecting file paths (or lists of file paths), you can interpolate environment variables using this syntax:

```yaml
csl: ${HOME}/mycsldir/special.csl
```

Special variables include:

- `${USERDATA}` -- resolves to the current user data directory when the defaults file is parsed
- `${.}` -- resolves to the directory containing the defaults file itself

### Example with Resource Paths

```yaml
epub-cover-image: ${.}/cover.jpg
epub-metadata: ${.}/meta.xml
resource-path:
  - .             # the working directory from which pandoc is run
  - ${.}/images   # the images subdirectory of the directory
                  # containing this defaults file
```

Note: Environment variable interpolation only works in fields expecting file paths.

## Placing Defaults Files

You can place defaults files in the `defaults` subdirectory of the user data directory for use from any location. For example, create `letter.yaml` in that subdirectory and invoke it with `pandoc --defaults letter` or `pandoc -dletter`.

## Combining Multiple Defaults

When using multiple defaults files, their contents are combined together.

## Combining with Command-Line Arguments

For repeatable command-line options (`--metadata-file`, `--css`, `--include-in-header`, `--include-before-body`, `--include-after-body`, `--variable`, `--metadata`, `--syntax-definition`), values specified on the command line combine with defaults file values rather than replacing them.

## Command-Line to Defaults File Mapping

| Command line | Defaults file |
|---|---|
| `foo.md` | `input-file: foo.md` |
| `foo.md bar.md` | `input-files:` followed by `- foo.md` and `- bar.md` |

The `input-files` value may be left empty to indicate stdin input, or set to an empty sequence `[]` for no input.

---

## 5.1 General options

| Command Line | Defaults File |
|---|---|
| `--from markdown+emoji` | `from: markdown+emoji` or `reader: markdown+emoji` |
| `--to markdown+hard_line_breaks` | `to: markdown+hard_line_breaks` or `writer: markdown+hard_line_breaks` |
| `--output foo.pdf` | `output-file: foo.pdf` |
| `--output -` | `output-file:` |
| `--data-dir dir` | `data-dir: dir` |
| `--defaults file` | `defaults:` with `- file` list entry |
| `--verbose` | `verbosity: INFO` |
| `--quiet` | `verbosity: ERROR` |
| `--fail-if-warnings` | `fail-if-warnings: true` |
| `--sandbox` | `sandbox: true` |
| `--log=FILE` | `log-file: FILE` |

### Priority Rules

Settings within a defaults file take precedence over those included via `defaults:` entries.

The `verbosity` setting accepts three values: `ERROR`, `WARNING`, or `INFO`.

---

## 5.2 Reader options

| Command Line | Defaults File |
|---|---|
| `--shift-heading-level-by -1` | `shift-heading-level-by: -1` |
| `--indented-code-classes python` | `indented-code-classes:` `- python` |
| `--default-image-extension ".jpg"` | `default-image-extension: '.jpg'` |
| `--file-scope` | `file-scope: true` |
| `--citeproc --lua-filter count-words.lua --filter special.lua` | `filters:` `- citeproc` `- count-words.lua` `- type: json` `path: special.lua` |
| `--metadata key=value --metadata key2` | `metadata:` `key: value` `key2: true` |
| `--metadata-file meta.yaml` | `metadata-files:` `- meta.yaml` OR `metadata-file: meta.yaml` |
| `--preserve-tabs` | `preserve-tabs: true` |
| `--tab-stop 8` | `tab-stop: 8` |
| `--track-changes accept` | `track-changes: accept` |
| `--extract-media dir` | `extract-media: dir` |
| `--abbreviations abbrevs.txt` | `abbreviations: abbrevs.txt` |
| `--trace` | `trace: true` |

Metadata values specified in a defaults file are parsed as literal string text, not Markdown.

Filters with `.lua` extension are treated as Lua filters; others default to JSON filters. Type specification is optional. Filters are run in the order specified. The citeproc filter can be invoked as `citeproc` or `{type: citeproc}`.

---

## 5.3 General writer options

| Command Line | Defaults File |
|---|---|
| `--standalone` | `standalone: true` |
| `--template letter` | `template: letter` |
| `--variable key=val --variable key2` | `variables: key: val; key2: true` |
| `--eol nl` | `eol: nl` |
| `--dpi 300` | `dpi: 300` |
| `--wrap preserve` | `wrap: "preserve"` |
| `--columns 72` | `columns: 72` |
| `--table-of-contents` | `table-of-contents: true` |
| `--toc` | `toc: true` |
| `--toc-depth 3` | `toc-depth: 3` |
| `--strip-comments` | `strip-comments: true` |
| `--no-highlight` | `syntax-highlighting: 'none'` |
| `--syntax-highlighting kate` | `syntax-highlighting: kate` |
| `--syntax-definition mylang.xml` | `syntax-definitions: - mylang.xml` |
| `--include-in-header inc.tex` | `include-in-header: - inc.tex` |
| `--include-before-body inc.tex` | `include-before-body: - inc.tex` |
| `--include-after-body inc.tex` | `include-after-body: - inc.tex` |
| `--resource-path .:foo` | `resource-path: ['.','foo']` |
| `--request-header foo:bar` | `request-headers: - ["User-Agent", "Mozilla/5.0"]` |
| `--no-check-certificate` | `no-check-certificate: true` |

---

## 5.4 Options affecting specific writers

| Command Line | Defaults File |
|---|---|
| `--self-contained` | `self-contained: true` |
| `--link-images` | `link-images: true` |
| `--html-q-tags` | `html-q-tags: true` |
| `--ascii` | `ascii: true` |
| `--reference-links` | `reference-links: true` |
| `--reference-location block` | `reference-location: block` |
| `--figure-caption-position=above` | `figure-caption-position: above` |
| `--table-caption-position=below` | `table-caption-position: below` |
| `--markdown-headings atx` | `markdown-headings: atx` |
| `--list-tables` | `list-tables: true` |
| `--top-level-division chapter` | `top-level-division: chapter` |
| `--number-sections` | `number-sections: true` |
| `--number-offset=1,4` | `number-offset: [1,4]` |
| `--listings` | `listings: true` |
| `--list-of-figures` | `list-of-figures: true` |
| `--lof` | `lof: true` |
| `--list-of-tables` | `list-of-tables: true` |
| `--lot` | `lot: true` |
| `--incremental` | `incremental: true` |
| `--slide-level 2` | `slide-level: 2` |
| `--section-divs` | `section-divs: true` |
| `--email-obfuscation references` | `email-obfuscation: references` |
| `--id-prefix ch1` | `identifier-prefix: ch1` |
| `--title-prefix MySite` | `title-prefix: MySite` |
| `--css styles/screen.css --css styles/special.css` | `css: [styles/screen.css, styles/special.css]` |
| `--reference-doc my.docx` | `reference-doc: my.docx` |
| `--epub-cover-image cover.jpg` | `epub-cover-image: cover.jpg` |
| `--epub-title-page=false` | `epub-title-page: false` |
| `--epub-metadata meta.xml` | `epub-metadata: meta.xml` |
| `--epub-embed-font special.otf --epub-embed-font headline.otf` | `epub-fonts: [special.otf, headline.otf]` |
| `--split-level 2` | `split-level: 2` |
| `--chunk-template="%i.html"` | `chunk-template: "%i.html"` |
| `--epub-subdirectory=""` | `epub-subdirectory: ''` |
| `--ipynb-output best` | `ipynb-output: best` |
| `--pdf-engine xelatex` | `pdf-engine: xelatex` |
| `--pdf-engine-opt=--shell-escape` | `pdf-engine-opts: ['-shell-escape']` or `pdf-engine-opt: '-shell-escape'` |

---

## 5.5 Citation rendering

| Command Line | Defaults File |
|---|---|
| `--citeproc` | `citeproc: true` |
| `--bibliography logic.bib` | `bibliography: logic.bib` |
| `--csl ieee.csl` | `csl: ieee.csl` |
| `--citation-abbreviations ab.json` | `citation-abbreviations: ab.json` |
| `--natbib` | `cite-method: natbib` |
| `--biblatex` | `cite-method: biblatex` |

The `cite-method` parameter accepts three values: `citeproc`, `natbib`, or `biblatex`. This setting exclusively impacts LaTeX output generation. Users intending to employ citeproc for citation formatting should simultaneously activate `citeproc: true`.

For managing the timing of citeproc processing relative to other filters, users should incorporate `citeproc` within the `filters` list as an alternative approach (consult Reader options documentation).

---

## 5.6 Math rendering in HTML

| Command Line | Defaults File |
|---|---|
| `--mathjax` | `html-math-method: {method: mathjax}` |
| `--mathml` | `html-math-method: {method: mathml}` |
| `--webtex` | `html-math-method: {method: webtex}` |
| `--katex` | `html-math-method: {method: katex}` |
| `--gladtex` | `html-math-method: {method: gladtex}` |

Beyond the methods listed above, the `method` field can also accept the value `plain`.

For command-line options that accept a URL argument, users can add an `url:` field within the `html-math-method:` configuration.

---

## 5.7 Options for wrapper scripts

| Command Line | Defaults File |
|---|---|
| `--dump-args` | `dump-args: true` |
| `--ignore-args` | `ignore-args: true` |
