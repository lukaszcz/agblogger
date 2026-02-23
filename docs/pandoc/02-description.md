# Description

Pandoc is a [Haskell](https://www.haskell.org) library for converting from one markup format to another, and a command-line tool that uses this library.

Pandoc can convert between numerous markup and word processing formats, including, but not limited to, various flavors of [Markdown](https://daringfireball.net/projects/markdown/), [HTML](https://www.w3.org/html/), [LaTeX](https://www.latex-project.org/) and [Word docx](https://en.wikipedia.org/wiki/Office_Open_XML). For the full lists of input and output formats, see the `--from` and `--to` options below. Pandoc can also produce [PDF](https://www.adobe.com/pdf/) output: see [Creating a PDF](#creating-a-pdf), below.

Pandoc's enhanced version of Markdown includes syntax for tables, definition lists, metadata blocks, footnotes, citations, math, and much more. See below under Pandoc's Markdown.

Pandoc has a modular design: it consists of a set of readers, which parse text in a given format and produce a native representation of the document (an _abstract syntax tree_ or AST), and a set of writers, which convert this native representation into a target format. Thus, adding an input or output format requires only adding a reader or writer. Users can also run custom [pandoc filters](https://pandoc.org/filters.html) to modify the intermediate AST.

Because pandoc's intermediate representation of a document is less expressive than many of the formats it converts between, one should not expect perfect conversions between every format and every other. Pandoc attempts to preserve the structural elements of a document, but not formatting details such as margin size. And some document elements, such as complex tables, may not fit into pandoc's simple document model. While conversions from pandoc's Markdown to all formats aspire to be perfect, conversions from formats more expressive than pandoc's Markdown can be expected to be lossy.

## Using pandoc

If no *input-files* are specified, input is read from *stdin*. Output goes to *stdout* by default. For output to a file, use the `-o`/`--output` option:

```
pandoc -o output.html input.txt
```

By default, pandoc produces a document fragment. To produce a standalone document (e.g. a valid HTML file including `<head>` and `<body>`), use the `-s` or `--standalone` flag:

```
pandoc -s -o output.html input.txt
```

For more information on how standalone documents are produced, see Templates below.

If multiple input files are given, pandoc will concatenate them all (with blank lines between them) before parsing. (Use `--file-scope` to parse files individually.)

## Specifying formats

The format of the input and output can be specified explicitly using command-line options. The input format can be specified using the `-f/--from` option, the output format using the `-t/--to` option. Thus, to convert `hello.txt` from Markdown to LaTeX, you could type:

```
pandoc -f markdown -t latex hello.txt
```

To convert `hello.html` from HTML to Markdown:

```
pandoc -f html -t markdown hello.html
```

Supported input and output formats are listed below under Options (see `-f` for input formats and `-t` for output formats). You can also use `pandoc --list-input-formats` and `pandoc --list-output-formats` to print lists of supported formats.

If the input or output format is not specified explicitly, pandoc will attempt to guess it from the extensions of the filenames. Thus, for example,

```
pandoc -o hello.tex hello.txt
```

will convert `hello.txt` from Markdown to LaTeX. If no output file is specified (so that output goes to *stdout*), or if the output file's extension is unknown, the output format will default to HTML. If no input file is specified (so that input comes from *stdin*), or if the input files' extensions are unknown, the input format will be assumed to be Markdown.

## Character encoding

Pandoc uses the UTF-8 character encoding for both input and output. If your local character encoding is not UTF-8, you should pipe input and output through [`iconv`](https://www.gnu.org/software/libiconv/):

```
iconv -t utf-8 input.txt | pandoc | iconv -f utf-8
```

Note that in some output formats (such as HTML, LaTeX, ConTeXt, RTF, OPML, DocBook, and Texinfo), information about the character encoding is included in the document header, which will only be included if you use the `-s/--standalone` option.

## Creating a PDF

To produce a PDF, specify an output file with a `.pdf` extension:

```
pandoc test.txt -o test.pdf
```

By default, pandoc uses LaTeX to create PDFs, which requires a LaTeX engine installation (see `--pdf-engine` below). Alternatively, pandoc can use ConTeXt, roff ms, or HTML as an intermediate format. To do this, specify a `.pdf` output file and add the `--pdf-engine` option or `-t context`, `-t html`, or `-t ms` to the command line. The `--pdf-engine` option specifies the tool used to generate the PDF from the intermediate format.

Control PDF styling using variables, depending on the intermediate format chosen: see variables for LaTeX, variables for ConTeXt, variables for `wkhtmltopdf`, or variables for ms. When using HTML as an intermediate format, style output with `--css`.

To debug PDF creation, examine the intermediate representation: instead of `-o test.pdf`, use `-s -o test.tex` to output generated LaTeX, then test with `pdflatex test.tex`.

When using LaTeX, these packages must be available (included with recent TeX Live versions): `amsfonts`, `amsmath`, `lm`, `unicode-math`, `iftex`, `listings` (if using `--listings`), `fancyvrb`, `longtable`, `booktabs`, `multirow` (for multi-row table cells), `graphicx` (for images), `bookmark`, `xcolor`, `soul`, `geometry` (with geometry variable), `setspace` (with linestretch), and `babel` (with lang). Additional packages needed: `xeCJK` for xelatex with CJKmainfont, `luatexja` for lualatex with CJKmainfont, `framed` (for colored code backgrounds), `fontspec` (for xelatex/lualatex), `selnolig` and `lua-ul` (for lualatex), `bidi` (for xelatex with dir variable), `mathspec` (for xelatex when mathspec variable is set), `csquotes` (for typography), `natbib`, `biblatex`, `bibtex`, `biber` (for citation rendering), and `cancel` (for cancel math). Optional packages improving quality: `upquote`, `microtype`, `parskip`, `xurl`, and `footnotehyper` or `footnote`.

## Reading from the Web

Instead of providing an input file, you can specify an absolute URI. In this scenario, pandoc will retrieve the content via HTTP:

```
pandoc -f html -t markdown https://www.fsf.org
```

You may also provide a custom User-Agent string or additional headers when requesting a document from a URL:

```
pandoc -f html -t markdown --request-header User-Agent:"Mozilla/5.0" \
  https://www.fsf.org
```
