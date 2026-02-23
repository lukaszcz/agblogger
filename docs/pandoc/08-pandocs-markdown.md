# Pandoc's Markdown

Pandoc implements an extended and slightly modified version of John Gruber's Markdown syntax. This section describes the syntax and highlights where it differs from the original Markdown specification.

The differences from standard Markdown can generally be disabled by using the `markdown_strict` format instead of `markdown`. Additionally, extensions can be individually enabled or disabled to provide more granular control over parsing behavior. These extensions are detailed in the sections that follow, alongside other extensions that are compatible with additional output formats.

## 8.1 Philosophy

Markdown prioritizes readability and simplicity in document creation. According to John Gruber, the foundational principle is:

> A Markdown-formatted document should be publishable as-is, as plain text, without looking like it's been marked up with tags or formatting instructions.

This philosophy has influenced pandoc's approach to syntax design for tables, footnotes, and other extensions.

However, pandoc diverges from original Markdown's intent in one significant way. While Markdown was built primarily for HTML output, pandoc supports multiple output formats. Consequently, pandoc discourages embedding raw HTML, instead offering alternative methods for representing crucial document components -- including definition lists, tables, mathematics expressions, and footnotes -- in a format-agnostic manner.

## 8.2 Paragraphs

A paragraph consists of one or more lines of text followed by one or more blank lines. Newlines function as spaces, allowing flexible paragraph reformatting. To create a hard line break, add two or more spaces at a line's end.

### 8.2.1 Extension: `escaped_line_breaks`

A backslash immediately before a newline also produces a hard line break. This method becomes necessary in multiline and grid table cells, where trailing spaces are disregarded, making it the sole approach for creating hard breaks in these contexts.

## 8.3 Headings

There are two kinds of headings: Setext and ATX.

### 8.3.1 Setext-style headings

A setext-style heading is a line of text "underlined" with a row of `=` signs (for level-one) or `-` signs (for level-two):

```
A level-one heading
===================

A level-two heading
-------------------
```

The heading text can contain inline formatting, such as emphasis.

### 8.3.2 ATX-style headings

An ATX-style heading consists of one to six `#` signs and a line of text, optionally followed by any number of `#` signs. The number of `#` signs at the beginning determines the heading level:

```
## A level-two heading

### A level-three heading ###
```

As with setext-style headings, the heading text can contain formatting:

```
# A level-one heading with a [link](/url) and *emphasis*
```

### 8.3.3 Extension: `blank_before_header`

Original Markdown syntax does not require a blank line before a heading. Pandoc requires this (except at the beginning of the document). This prevents `#` characters from accidentally appearing at line starts through line wrapping.

### 8.3.4 Extension: `space_in_atx_header`

Many Markdown implementations don't require a space between opening `#`s and heading text. With this extension, pandoc requires the space.

### 8.3.5 Heading identifiers

See the `auto_identifiers` extension.

### 8.3.6 Extension: `header_attributes`

Headings can be assigned attributes using this syntax at the end of the line:

```
{#identifier .class .class key=value key=value}
```

Examples:

```
# My heading {#foo}

## My heading ##    {#foo}

My other heading   {#foo}
---------------
```

This syntax is compatible with PHP Markdown Extra. Identifiers, classes, and key/value attributes are used in HTML and HTML-based formats such as EPUB and slidy.

Headings with the `unnumbered` class won't be numbered with `--number-sections`. A single hyphen (`-`) is equivalent to `.unnumbered`:

```
# My heading {-}
```

If `unlisted` class appears with `unnumbered`, the heading won't appear in table of contents.

### 8.3.7 Extension: `implicit_header_references`

Pandoc behaves as if reference links have been defined for each heading. To link to a heading like:

```
# Heading identifiers in HTML
```

You can write:

```
[Heading identifiers in HTML]
```

or

```
[Heading identifiers in HTML][]
```

or

```
[the section on heading identifiers][heading identifiers in HTML]
```

Multiple headings with identical text will have the reference link to the first one only. Explicit link references take priority over implicit heading references.

## 8.4 Block quotations

Markdown uses email conventions for quoting blocks of text. A block quotation consists of one or more paragraphs or other block elements (such as lists or headings), with each line preceded by a `>` character and an optional space. The `>` does not need to start at the left margin, but should not be indented more than three spaces.

```
> This is a block quote. This
> paragraph has two lines.
>
> 1. This is a list inside a block quote.
> 2. Second item.
```

A "lazy" form is also allowed, which requires the `>` character only on the first line of each block:

```
> This is a block quote. This
paragraph has two lines.

> 1. This is a list inside a block quote.
2. Second item.
```

Block quotes can be nested, as other block quotes can be contained within them:

```
> This is a block quote.
>
> > A block quote within a block quote.
```

When the `>` character is followed by an optional space, that space becomes part of the block quote marker rather than the content indentation. To include an indented code block in a block quote, you need five spaces after the `>`:

```
>     code
```

### 8.4.1 Extension: `blank_before_blockquote`

Original Markdown does not require a blank line before a block quote. Pandoc requires this (except at the document beginning). This requirement exists because a `>` can accidentally appear at the start of a line through various means. Unless using `markdown_strict` format, the following does not create a nested block quote in pandoc:

```
> This is a block quote.
>> Not nested, since `blank_before_blockquote` is enabled by default
```

## 8.5 Verbatim (code) blocks

### 8.5.1 Indented code blocks

A block of text indented four spaces (or one tab) is treated as verbatim text: that is, special characters do not trigger special formatting, and all spaces and line breaks are preserved. For example,

```
if (a > 3) {
  moveShip(5 * gravity, DOWN);
}
```

The initial (four space or one tab) indentation is not considered part of the verbatim text, and is removed in the output.

Note: blank lines in the verbatim text need not begin with four spaces.

### 8.5.2 Fenced code blocks

### 8.5.3 Extension: `fenced_code_blocks`

In addition to standard indented code blocks, pandoc supports _fenced_ code blocks. These begin with a row of three or more tildes (`~`) and end with a row of tildes that must be at least as long as the starting row. Everything between these lines is treated as code. No indentation is necessary:

```
~~~~~~~
if (a > 3) {
  moveShip(5 * gravity, DOWN);
}
~~~~~~~
```

Like regular code blocks, fenced code blocks must be separated from surrounding text by blank lines.

If the code itself contains a row of tildes or backticks, just use a longer row of tildes or backticks at the start and end:

```
~~~~~~~~~~~~~~~~
~~~~~~~~~~
code including tildes
~~~~~~~~~~
~~~~~~~~~~~~~~~~
```

### 8.5.4 Extension: `backtick_code_blocks`

Same as `fenced_code_blocks`, but uses backticks (`` ` ``) instead of tildes (`~`).

### 8.5.5 Extension: `fenced_code_attributes`

Optionally, you may attach attributes to fenced or backtick code block using this syntax:

```
~~~~ {#mycode .haskell .numberLines startFrom="100"}
qsort []     = []
qsort (x:xs) = qsort (filter (< x) xs) ++ [x] ++
               qsort (filter (>= x) xs)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```

Here `mycode` is an identifier, `haskell` and `numberLines` are classes, and `startFrom` is an attribute with value `100`. Some output formats can use this information to do syntax highlighting. Currently, the only output formats that use this information are HTML, LaTeX, Docx, Ms, and PowerPoint. If highlighting is supported for your output format and language, then the code block above will appear highlighted, with numbered lines. (To see which languages are supported, type `pandoc --list-highlight-languages`.) Otherwise, the code block above will appear as follows:

```html
<pre id="mycode" class="haskell numberLines" startFrom="100">
  <code>
  ...
  </code>
</pre>
```

The `numberLines` (or `number-lines`) class will cause the lines of the code block to be numbered, starting with `1` or the value of the `startFrom` attribute. The `lineAnchors` (or `line-anchors`) class will cause the lines to be clickable anchors in HTML output.

A shortcut form can also be used for specifying the language of the code block:

    ```haskell
    qsort [] = []
    ```

This is equivalent to:

    ``` {.haskell}
    qsort [] = []
    ```

This shortcut form may be combined with attributes:

    ```haskell {.numberLines}
    qsort [] = []
    ```

Which is equivalent to:

    ``` {.haskell .numberLines}
    qsort [] = []
    ```

If the `fenced_code_attributes` extension is disabled, but input contains class attribute(s) for the code block, the first class attribute will be printed after the opening fence as a bare word.

To prevent all highlighting, use the `--syntax-highlighting=none` option. To set the highlighting style or method, use `--syntax-highlighting`. For more information on highlighting, see Syntax highlighting, below.

## 8.6 Line blocks

### 8.6.1 Extension: `line_blocks`

A line block is a sequence of lines beginning with a vertical bar (`|`) followed by a space. The division into lines will be preserved in the output, as will any leading spaces; otherwise, the lines will be formatted as Markdown. This is useful for verse and addresses:

```
| The limerick packs laughs anatomical
| In space that is quite economical.
|    But the good ones I've seen
|    So seldom are clean
| And the clean ones so seldom are comical

| 200 Main St.
| Berkeley, CA 94718
```

The lines can be hard-wrapped if needed, but the continuation line must begin with a space.

```
| The Right Honorable Most Venerable and Righteous Samuel L.
  Constable, Jr.
| 200 Main St.
| Berkeley, CA 94718
```

Inline formatting (such as emphasis) is allowed in the content (though it can't cross line boundaries). Block-level formatting (such as block quotes or lists) is not recognized.

This syntax is borrowed from [reStructuredText](https://docutils.sourceforge.io/docs/ref/rst/introduction.html).

## 8.7 Lists

### 8.7.1 Bullet lists

A bullet list comprises items marked with bullets (`*`, `+`, or `-`). Basic example:

```
* one
* two
* three
```

This creates a "compact" list. For a "loose" list where each item formats as a paragraph, add spaces between items:

```
* one

* two

* three
```

Bullets can be indented one to three spaces and must be followed by whitespace. Subsequent lines align best with the first line after the bullet:

```
* here is my first
  list item.
* and my second.
```

Markdown also permits "lazy" formatting:

```
* here is my first
list item.
* and my second.
```

### 8.7.2 Block content in list items

List items may contain multiple paragraphs and block-level content. Subsequent paragraphs require a blank line and indentation aligning with the first non-space content after the list marker:

```
  * First paragraph.

    Continued.

  * Second paragraph. With a code block, which must be indented
    eight spaces:

        { code }
```

Exception: when a list marker is followed by an indented code block (beginning 5 spaces after the marker), subsequent paragraphs must start two columns after the list marker's last character:

```
*     code

  continuation paragraph
```

Nested lists are supported. The preceding blank line is optional, and the nested list must indent to align with the first non-space character after the containing item's marker:

```
* fruits
  + apples
    - macintosh
    - red delicious
  + pears
  + peaches
* vegetables
  + broccoli
  + chard
```

Lazy formatting is permitted, though the first line of each paragraph or block in multi-paragraph items must be indented:

```
+ A lazy, lazy, list
item.

+ Another one; this looks
bad but is legal.

    Second paragraph of second
list item.
```

### 8.7.3 Ordered lists

Ordered lists function like bulleted lists, but items begin with enumerators rather than bullets.

In original Markdown, enumerators are decimal numbers followed by a period and space. The actual numbers are ignored:

```
1.  one
2.  two
3.  three
```

produces identical output to:

```
5.  one
7.  two
1.  three
```

### 8.7.4 Extension: `fancy_lists`

Pandoc permits ordered list items marked with uppercase and lowercase letters and Roman numerals, plus Arabic numerals. List markers may be enclosed in parentheses or followed by a right-parenthesis or period. They require at least one space separation from following text (or two spaces if the marker is a capital letter with a period).

The `fancy_lists` extension allows `#` as an ordered list marker:

```
#. one
#. two
```

Note: the `#` marker doesn't work with `commonmark`.

### 8.7.5 Extension: `startnum`

Pandoc preserves list marker type and starting number where possible in output. This example yields numbers with parentheses starting at 9, with a lowercase Roman numeral sublist:

```
 9)  Ninth
10)  Tenth
11)  Eleventh
       i. subone
      ii. subtwo
     iii. subthree
```

Different marker types trigger new lists:

```
(2) Two
(5) Three
1.  Four
*   Five
```

For default markers, use `#.`:

```
#.  one
#.  two
#.  three
```

### 8.7.6 Extension: `task_lists`

Pandoc supports task lists using GitHub-Flavored Markdown syntax:

```
- [ ] an unchecked task list item
- [x] checked item
```

### 8.7.7 Definition lists

### 8.7.8 Extension: `definition_lists`

Pandoc supports definition lists using PHP Markdown Extra syntax with extensions:

```
Term 1

:   Definition 1

Term 2 with *inline markup*

:   Definition 2

        { some code, part of Definition 2 }

    Third paragraph of definition 2.
```

Each term must fit on one line, optionally followed by a blank line, then one or more definitions. Definitions begin with a colon or tilde, optionally indented one or two spaces.

Terms may have multiple definitions; each consists of one or more block elements indented four spaces or one tab. The definition body should be indented four spaces. Lazy indentation is permitted except at paragraph or block element beginnings:

```
Term 1

:   Definition
with lazy continuation.

    Second paragraph of the definition.
```

Omit space before the definition for compact formatting:

```
Term 1
  ~ Definition 1

Term 2
  ~ Definition 2a
  ~ Definition 2b
```

Space between definition list items is required.

### 8.7.9 Numbered example lists

### 8.7.10 Extension: `example_lists`

The special marker `@` creates sequentially numbered examples. The first item marked with `@` becomes '(1)', the next '(2)', and so on throughout the document:

```
(@)  My first example will be numbered (1).
(@)  My second example will be numbered (2).

Explanation of examples.

(@)  My third example will be numbered (3).
```

Examples may be labeled and referenced:

```
(@good)  This is a good example.

As (@good) illustrates, ...
```

Labels contain alphanumeric characters, underscores, or hyphens.

Continuation paragraphs in example lists must always be indented four spaces, regardless of marker length. This is because example labels tend to be long.

Earlier numbered examples may be repeated by reusing their label:

```
(@foo) Sample sentence.

Intervening text...

This theory can explain the case we saw earlier (repeated):

(@foo) Sample sentence.
```

This works reliably only if the repeated item is in a list by itself.

### 8.7.11 Ending a list

To add an indented code block after a list without it being treated as list item content, insert non-indented content like an HTML comment:

```
-   item one
-   item two

<!-- end of list -->

    { my code block }
```

This technique also separates consecutive lists:

```
1.  one
2.  two
3.  three

<!-- -->

1.  uno
2.  dos
3.  tres
```

## 8.8 Horizontal rules

A line containing a row of three or more `*`, `-`, or `_` characters (optionally separated by spaces) produces a horizontal rule:

```
*  *  *  *

---------------
```

We strongly recommend that horizontal rules be separated from surrounding text by blank lines. If a horizontal rule is not followed by a blank line, pandoc may try to interpret the lines that follow as a YAML metadata block or a table.

## 8.9 Tables

Four kinds of tables may be used. The first three kinds presuppose the use of a fixed-width font, such as Courier. The fourth kind can be used with proportionally spaced fonts, as it does not require lining up columns.

### 8.9.1 Extension: `table_captions`

A caption may optionally be provided with all 4 kinds of tables (as illustrated in the examples below). A caption is a paragraph beginning with the string `Table:` (or `table:` or just `:`), which will be stripped off. It may appear either before or after the table.

### 8.9.2 Extension: `simple_tables`

Simple tables look like this:

```
  Right     Left     Center     Default
-------     ------ ----------   -------
     12     12        12            12
    123     123       123          123
      1     1          1             1

Table:  Demonstration of simple table syntax.
```

The header and table rows must each fit on one line. Column alignments are determined by the position of the header text relative to the dashed line below it:

- If the dashed line is flush with the header text on the right side but extends beyond it on the left, the column is right-aligned.
- If the dashed line is flush with the header text on the left side but extends beyond it on the right, the column is left-aligned.
- If the dashed line extends beyond the header text on both sides, the column is centered.
- If the dashed line is flush with the header text on both sides, the default alignment is used (in most cases, this will be left).

The table must end with a blank line, or a line of dashes followed by a blank line.

The column header row may be omitted, provided a dashed line is used to end the table. For example:

```
-------     ------ ----------   -------
     12     12        12             12
    123     123       123           123
      1     1          1              1
-------     ------ ----------   -------
```

When the header row is omitted, column alignments are determined on the basis of the first line of the table body. So, in the tables above, the columns would be right, left, center, and right aligned, respectively.

### 8.9.3 Extension: `multiline_tables`

Multiline tables allow header and table rows to span multiple lines of text (but cells that span multiple columns or rows of the table are not supported). Here is an example:

```
-------------------------------------------------------------
 Centered   Default           Right Left
  Header    Aligned         Aligned Aligned
----------- ------- --------------- -------------------------
   First    row                12.0 Example of a row that
                                    spans multiple lines.

  Second    row                 5.0 Here's another one. Note
                                    the blank line between
                                    rows.
-------------------------------------------------------------

Table: Here's the caption. It, too, may span
multiple lines.
```

These work like simple tables, but with the following differences:

- They must begin with a row of dashes, before the header text (unless the header row is omitted).
- They must end with a row of dashes, then a blank line.
- The rows must be separated by blank lines.

In multiline tables, the table parser pays attention to the widths of the columns, and the writers try to reproduce these relative widths in the output. So, if you find that one of the columns is too narrow in the output, try widening it in the Markdown source.

The header may be omitted in multiline tables as well as simple tables:

```
----------- ------- --------------- -------------------------
   First    row                12.0 Example of a row that
                                    spans multiple lines.

  Second    row                 5.0 Here's another one. Note
                                    the blank line between
                                    rows.
----------- ------- --------------- -------------------------

: Here's a multiline table without a header.
```

It is possible for a multiline table to have just one row, but the row should be followed by a blank line (and then the row of dashes that ends the table), or the table may be interpreted as a simple table.

### 8.9.4 Extension: `grid_tables`

Grid tables look like this:

```
: Sample grid table.

+---------------+---------------+--------------------+
| Fruit         | Price         | Advantages         |
+===============+===============+====================+
| Bananas       | $1.34         | - built-in wrapper |
|               |               | - bright color     |
+---------------+---------------+--------------------+
| Oranges       | $2.10         | - cures scurvy     |
|               |               | - tasty            |
+---------------+---------------+--------------------+
```

The row of `=`s separates the header from the table body, and can be omitted for a headerless table. The cells of grid tables may contain arbitrary block elements (multiple paragraphs, code blocks, lists, etc.).

Cells can span multiple columns or rows:

```
+---------------------+----------+
| Property            | Earth    |
+=============+=======+==========+
|             | min   | -89.2 °C |
| Temperature +-------+----------+
| 1961-1990   | mean  | 14 °C    |
|             +-------+----------+
|             | max   | 56.7 °C  |
+-------------+-------+----------+
```

A table header may contain more than one row:

```
+---------------------+-----------------------+
| Location            | Temperature 1961-1990 |
|                     | in degree Celsius     |
|                     +-------+-------+-------+
|                     | min   | mean  | max   |
+=====================+=======+=======+=======+
| Antarctica          | -89.2 | N/A   | 19.8  |
+---------------------+-------+-------+-------+
| Earth               | -89.2 | 14    | 56.7  |
+---------------------+-------+-------+-------+
```

Alignments can be specified as with pipe tables, by putting colons at the boundaries of the separator line after the header:

```
+---------------+---------------+--------------------+
| Right         | Left          | Centered           |
+==============:+:==============+:==================:+
| Bananas       | $1.34         | built-in wrapper   |
+---------------+---------------+--------------------+
```

For headerless tables, the colons go on the top line instead:

```
+--------------:+:--------------+:------------------:+
| Right         | Left          | Centered           |
+---------------+---------------+--------------------+
```

A table foot can be defined by enclosing it with separator lines that use `=` instead of `-`:

```
+---------------+---------------+
| Fruit         | Price         |
+===============+===============+
| Bananas       | $1.34         |
+---------------+---------------+
| Oranges       | $2.10         |
+===============+===============+
| Sum           | $3.44         |
+===============+===============+
```

The foot must always be placed at the very bottom of the table.

Grid tables can be created easily using Emacs' table-mode (`M-x table-insert`).

### 8.9.5 Extension: `pipe_tables`

Pipe tables look like this:

```
| Right | Left | Default | Center |
|------:|:-----|---------|:------:|
|   12  |  12  |    12   |    12  |
|  123  |  123 |   123   |   123  |
|    1  |    1 |     1   |     1  |

  : Demonstration of pipe table syntax.
```

The syntax is identical to PHP Markdown Extra tables. The beginning and ending pipe characters are optional, but pipes are required between all columns. The colons indicate column alignment as shown. The header cannot be omitted. To simulate a headerless table, include a header with blank cells.

Since the pipes indicate column boundaries, columns need not be vertically aligned, as they are in the above example. So, this is a perfectly legal (though ugly) pipe table:

```
fruit| price
-----|-----:
apple|2.05
pear|1.37
orange|3.09
```

The cells of pipe tables cannot contain block elements like paragraphs and lists, and cannot span multiple lines. If any line of the Markdown source is longer than the column width (see `--columns`), then the table will take up the full text width and the cell contents will wrap, with the relative cell widths determined by the number of dashes in the line separating the table header from the table body. (For example `---|-` would make the first column 3/4 and the second column 1/4 of the full text width.) On the other hand, if no lines are wider than column width, then cell contents will not be wrapped, and the cells will be sized to their contents.

Note: pandoc also recognizes pipe tables of the following form, as can be produced by Emacs' orgtbl-mode:

```
| One | Two   |
|-----+-------|
| my  | table |
| is  | nice  |
```

The difference is that `+` is used instead of `|`. Other orgtbl features are not supported. In particular, to get non-default column alignment, you'll need to add colons as above.

### 8.9.6 Extension: `table_attributes`

Attributes may be attached to tables by including them at the end of the caption. (For the syntax, see `header_attributes`.)

```
  : Here's the caption. {#ident .class key="value"}
```

## 8.10 Metadata blocks

### 8.10.1 Extension: `pandoc_title_block`

If the file begins with a title block:

```
% title
% author(s) (separated by semicolons)
% date
```

It will be parsed as bibliographic information, not regular text. (It will be used, for example, in the title of standalone LaTeX or HTML output.) The block may contain just a title, a date and an author, or all three elements. If you want to include an author but no title, or a title and a date but no author, you need a blank line:

```
%
% Author
```

```
% My title
%
% June 15, 2006
```

The title may occupy multiple lines, but continuation lines must begin with leading space, thus:

```
% My title
  on multiple lines
```

If a document has multiple authors, the authors may be put on separate lines with leading space, or separated by semicolons, or both. So, all of the following are equivalent:

```
% Author One
  Author Two
```

```
% Author One; Author Two
```

```
% Author One;
  Author Two
```

The date must fit on one line.

All three metadata fields may contain standard inline formatting (italics, links, footnotes, etc.).

Title blocks will always be parsed, but they will affect the output only when the `--standalone` (`-s`) option is chosen. In HTML output, titles will appear twice: once in the document head -- this is the title that will appear at the top of the window in a browser -- and once at the beginning of the document body. The title in the document head can have an optional prefix attached (`--title-prefix` or `-T` option). The title in the body appears as an H1 element with class "title", so it can be suppressed or reformatted with CSS. If a title prefix is specified with `-T` and no title block appears in the document, the title prefix will be used by itself as the HTML title.

The man page writer extracts a title, man page section number, and other header and footer information from the title line. The title is assumed to be the first word on the title line, which may optionally end with a (single-digit) section number in parentheses. (There should be no space between the title and the parentheses.) Anything after this is assumed to be additional footer and header text. A single pipe character (`|`) should be used to separate the footer text from the header text. Thus:

```
% PANDOC(1)
```

will yield a man page with the title `PANDOC` and section 1.

```
% PANDOC(1) Pandoc User Manuals
```

will also have "Pandoc User Manuals" in the footer.

```
% PANDOC(1) Pandoc User Manuals | Version 4.0
```

will also have "Version 4.0" in the header.

### 8.10.2 Extension: `yaml_metadata_block`

A YAML metadata block is a valid YAML object, delimited by a line of three hyphens (`---`) at the top and a line of three hyphens (`---`) or three dots (`...`) at the bottom. The initial line `---` must not be followed by a blank line. A YAML metadata block may occur anywhere in the document, but if it is not at the beginning, it must be preceded by a blank line.

Note that, because of the way pandoc concatenates input files when several are provided, you may also keep the metadata in a separate YAML file and pass it to pandoc as an argument, along with your Markdown files:

```
pandoc chap1.md chap2.md chap3.md metadata.yaml -s -o book.html
```

Just be sure that the YAML file begins with `---` and ends with `---` or `...`. Alternatively, you can use the `--metadata-file` option. Using that approach however, you cannot reference content (like footnotes) from the main Markdown input document.

Metadata will be taken from the fields of the YAML object and added to any existing document metadata. Metadata can contain lists and objects (nested arbitrarily), but all string scalars will be interpreted as Markdown. Fields with names ending in an underscore will be ignored by pandoc. (They may be given a role by external processors.) Field names must not be interpretable as YAML numbers or boolean values (so, for example, `yes`, `True`, and `15` cannot be used as field names).

A document may contain multiple metadata blocks. If two metadata blocks attempt to set the same field, the value from the second block will be taken.

Each metadata block is handled internally as an independent YAML document. This means, for example, that any YAML anchors defined in a block cannot be referenced in another block.

When pandoc is used with `-t markdown` to create a Markdown document, a YAML metadata block will be produced only if the `-s/--standalone` option is used. All of the metadata will appear in a single block at the beginning of the document.

Note that YAML escaping rules must be followed. Thus, for example, if a title contains a colon, it must be quoted, and if it contains a backslash escape, then it must be ensured that it is not treated as a YAML escape sequence. The pipe character (`|`) can be used to begin an indented block that will be interpreted literally, without need for escaping. This form is necessary when the field contains blank lines or block-level formatting:

```yaml
---
title:  'This is the title: it contains a colon'
author:
- Author One
- Author Two
keywords: [nothing, nothingness]
abstract: |
  This is the abstract.

  It consists of two paragraphs.
...
```

The literal block after the `|` must be indented relative to the line containing the `|`. If it is not, the YAML will be invalid and pandoc will not interpret it as metadata. For an overview of the complex rules governing YAML, see the Wikipedia entry on YAML syntax.

Template variables will be set automatically from the metadata. Thus, for example, in writing HTML, the variable `abstract` will be set to the HTML equivalent of the Markdown in the `abstract` field:

```html
<p>This is the abstract.</p>
<p>It consists of two paragraphs.</p>
```

Variables can contain arbitrary YAML structures, but the template must match this structure. The `author` variable in the default templates expects a simple list or string, but can be changed to support more complicated structures. The following combination, for example, would add an affiliation to the author if one is given:

```yaml
---
title: The document title
author:
- name: Author One
  affiliation: University of Somewhere
- name: Author Two
  affiliation: University of Nowhere
...
```

To use the structured authors in the example above, you would need a custom template:

```
$for(author)$
$if(author.name)$
$author.name$$if(author.affiliation)$ ($author.affiliation$)$endif$
$else$
$author$
$endif$
$endfor$
```

Raw content to include in the document's header may be specified using `header-includes`; however, it is important to mark up this content as raw code for a particular output format, using the `raw_attribute` extension, or it will be interpreted as Markdown. For example:

```yaml
header-includes:
- |
  ```{=latex}
  \let\oldsection\section
  \renewcommand{\section}[1]{\clearpage\oldsection{#1}}
  ```
```

Note: the `yaml_metadata_block` extension works with `commonmark` as well as `markdown` (and it is enabled by default in `gfm` and `commonmark_x`). However, in these formats the following restrictions apply:

- The YAML metadata block must occur at the beginning of the document (and there can be only one). If multiple files are given as arguments to pandoc, only the first can be a YAML metadata block.
- The leaf nodes of the YAML structure are parsed in isolation from each other and from the rest of the document. So, for example, you can't use a reference link in these contexts if the link definition is somewhere else in the document.

## 8.11 Backslash escapes

### 8.11.1 Extension: `all_symbols_escapable`

Any punctuation or space character preceded by a backslash will be treated literally, even if it would normally indicate formatting, except inside code blocks or inline code. For example:

```
*\*hello\**
```

produces:

```
<em>*hello*</em>
```

instead of:

```
<strong>hello</strong>
```

This rule differs from original Markdown, which allows backslash-escaping only for these characters:

```
\`*_{}[]()>#+-.!
```

(Note: the `markdown_strict` format uses the original Markdown rule.)

A backslash-escaped space becomes a nonbreaking space. In TeX output, it renders as `~`. In HTML and XML output, it appears as a literal unicode nonbreaking space character.

A backslash-escaped newline (backslash at line end) creates a hard line break, appearing as `\\` in TeX output and `<br />` in HTML. This offers an alternative to Markdown's two trailing spaces method.

Backslash escapes do not work in verbatim contexts.

## 8.12 Inline formatting

### 8.12.1 Emphasis

To emphasize text, surround it with `*`s or `_`:

```
This text is _emphasized with underscores_, and this
is *emphasized with asterisks*.
```

Double `*` or `_` produces **strong emphasis**:

```
This is **strong emphasis** and __with underscores__.
```

A `*` or `_` character surrounded by spaces, or backslash-escaped, will not trigger emphasis:

```
This is * not emphasized *, and \*neither is this\*.
```

### 8.12.2 Extension: `intraword_underscores`

Because `_` is sometimes used inside words and identifiers, pandoc does not interpret a `_` surrounded by alphanumeric characters as an emphasis marker. If you want to emphasize just part of a word, use `*`:

```
feas*ible*, not feas*able*.
```

### 8.12.3 Strikeout

### 8.12.4 Extension: `strikeout`

To strike out a section of text with a horizontal line, begin and end it with `~~`:

```
This ~~is deleted text.~~
```

### 8.12.5 Superscripts and subscripts

### 8.12.6 Extension: `superscript`, `subscript`

Superscripts may be written by surrounding the superscripted text by `^` characters; subscripts may be written by surrounding the subscripted text by `~` characters:

```
H~2~O is a liquid.  2^10^ is 1024.
```

The text between `^...^` or `~...~` may not contain spaces or newlines. If the superscripted or subscripted text contains spaces, these spaces must be escaped with backslashes. Thus, if you want the letter P with 'a cat' in subscripts, use `P~a\ cat~`, not `P~a cat~`.

### 8.12.7 Verbatim

To make a short span of text verbatim, put it inside backticks:

```
What is the difference between `>>=` and `>>`?
```

If the verbatim text includes a backtick, use double backticks:

```
Here is a literal backtick `` ` ``.
```

(The spaces after the opening backticks and before the closing backticks will be ignored.)

The general rule is that a verbatim span starts with a string of consecutive backticks (optionally followed by a space) and ends with a string of the same number of backticks (optionally preceded by a space).

Note that backslash-escapes (and other Markdown constructs) do not work in verbatim contexts:

```
This is a backslash followed by an asterisk: `\*`.
```

### 8.12.8 Extension: `inline_code_attributes`

Attributes can be attached to verbatim text, just as with fenced code blocks:

```
`<$>`{.haskell}
```

### 8.12.9 Underline

To underline text, use the `underline` class:

```
[Underline]{.underline}
```

Or, without the `bracketed_spans` extension (but with `native_spans`):

```
<span class="underline">Underline</span>
```

This will work in all output formats that support underline.

### 8.12.10 Small caps

To write small caps, use the `smallcaps` class:

```
[Small caps]{.smallcaps}
```

Or, without the `bracketed_spans` extension:

```
<span class="smallcaps">Small caps</span>
```

For compatibility with other Markdown flavors, CSS is also supported:

```
<span style="font-variant:small-caps;">Small caps</span>
```

This will work in all output formats that support small caps.

### 8.12.11 Highlighting

To highlight text, use the `mark` class:

```
[Mark]{.mark}
```

Or, without the `bracketed_spans` extension (but with `native_spans`):

```
<span class="mark">Mark</span>
```

This will work in all output formats that support highlighting.

## 8.13 Math

### 8.13.1 Extension: `tex_math_dollars`

Text enclosed between two `$` characters is processed as TeX math. The opening `$` requires a non-space character immediately to its right, and the closing `$` requires a non-space character to its left and cannot be followed by a digit. For example, `$20,000 and $30,000` will not be parsed as math. To include literal `$` characters, use backslash escaping.

Display math uses `$$` delimiters, which may have whitespace around the formula but cannot have blank lines between opening and closing delimiters.

### Rendering by output format

- **LaTeX**: Appears verbatim surrounded by `\(...\)` (inline) or `\[...\]` (display)
- **Markdown, Emacs Org mode, ConTeXt, ZimWiki**: Appears verbatim surrounded by `$...$` (inline) or `$$...$$` (display)
- **XWiki**: Rendered verbatim surrounded by `{{formula}}..{{/formula}}`
- **reStructuredText**: Rendered using an interpreted text role `:math:`
- **AsciiDoc**: Appears verbatim in `latexmath:[...]`
- **Texinfo**: Rendered inside `@math` command
- **roff man, Jira markup**: Rendered verbatim without `$` delimiters
- **MediaWiki, DokuWiki**: Rendered inside `<math>` tags
- **Textile**: Rendered inside `<span class="math">` tags
- **RTF, OpenDocument**: Rendered using Unicode characters when possible, otherwise verbatim
- **ODT**: Rendered using MathML when possible
- **DocBook**: Uses MathML with `--mathml` flag; otherwise Unicode characters
- **Docx and PowerPoint**: Rendered using OMML math markup
- **FictionBook2**: Uses CodeCogs web service with `--webtex` option; otherwise verbatim
- **HTML, Slidy, DZSlides, S5, EPUB**: See Math rendering in HTML section

## 8.14 Raw HTML

### 8.14.1 Extension: `raw_html`

Markdown enables insertion of raw HTML or DocBook anywhere in a document, except in verbatim contexts where `<`, `>`, and `&` are treated literally. While technically standard Markdown supports this, it's been designated an extension for selective disabling.

The raw HTML passes through unchanged in HTML, S5, Slidy, Slideous, DZSlides, EPUB, Markdown, CommonMark, Emacs Org mode, and Textile output, but is suppressed in other formats.

For more explicit raw HTML inclusion, consult the `raw_attribute` extension.

In CommonMark format with `raw_html` enabled, superscripts, subscripts, strikeouts and small capitals render as HTML. Otherwise plain-text fallbacks are used. Even with `raw_html` disabled, tables render with HTML syntax when pipe syntax cannot be used.

### 8.14.2 Extension: `markdown_in_html_blocks`

Original Markdown requires HTML blocks to be separated from surrounding text with blank lines and aligned at the left margin. Within these blocks, all content is interpreted as HTML, not Markdown.

Pandoc uses this behavior with `markdown_strict` format; by default, pandoc interprets material between HTML block tags as Markdown. For example:

```html
<table>
<tr>
<td>*one*</td>
<td>[a link](https://google.com)</td>
</tr>
</table>
```

becomes:

```html
<table>
<tr>
<td><em>one</em></td>
<td><a href="https://google.com">a link</a></td>
</tr>
</table>
```

An exception exists: text within `<script>`, `<style>`, `<pre>`, and `<textarea>` tags is not interpreted as Markdown.

This departure from original Markdown facilitates mixing Markdown with HTML block elements, allowing `<div>` tag wrapping without preventing Markdown interpretation.

### 8.14.3 Extension: `native_divs`

Native pandoc `Div` blocks are used for content inside `<div>` tags. Output generally matches `markdown_in_html_blocks`, but enables easier pandoc filter writing for manipulating block groups.

### 8.14.4 Extension: `native_spans`

Native pandoc `Span` blocks are used for content inside `<span>` tags. Output typically matches `raw_html`, but facilitates pandoc filter writing for manipulating inline groups.

### 8.14.5 Extension: `raw_tex`

Pandoc allows raw LaTeX, TeX, and ConTeXt inclusion in documents. Inline TeX commands are preserved unchanged for LaTeX and ConTeXt writers. For example, LaTeX can include BibTeX citations:

```
This result was proved in \cite{jones.1967}.
```

In LaTeX environments:

```
\begin{tabular}{|l|l|}\hline
Age & Frequency \\ \hline
18--25  & 15 \\
26--35  & 33 \\
36--45  & 22 \\ \hline
\end{tabular}
```

Material between begin and end tags is interpreted as raw LaTeX, not Markdown.

For more explicit raw TeX inclusion, see the `raw_attribute` extension.

Inline LaTeX is ignored in output formats other than Markdown, LaTeX, Emacs Org mode, and ConTeXt.

### 8.14.6 Generic raw attribute

### 8.14.7 Extension: `raw_attribute`

Inline spans and fenced code blocks with special attributes parse as raw content in designated formats. Examples include raw roff `ms` blocks:

    ```{=ms}
    .MYMACRO
    blah blah
    ```

And raw `html` inline elements:

```
This is `<a>html</a>`{=html}
```

Raw XML can be inserted into `docx` documents, such as pagebreaks:

    ```{=openxml}
    <w:p>
      <w:r>
        <w:br w:type="page"/>
      </w:r>
    </w:p>
    ```

Format names should match target format names (see `-t/--to`). Use `openxml` for `docx`, `opendocument` for `odt`, `html5` for `epub3`, `html4` for `epub2`, and `latex`, `beamer`, `ms`, or `html5` for `pdf` (depending on `--pdf-engine`).

This extension requires enabling the relevant inline code or fenced code block type. The raw attribute cannot combine with regular attributes.

## 8.15 LaTeX macros

### 8.15.1 Extension: `latex_macros`

When this extension is enabled, pandoc will parse LaTeX macro definitions and apply the resulting macros to all LaTeX math and raw LaTeX. So, for example, the following will work in all output formats, not just LaTeX:

```
\newcommand{\tuple}[1]{\langle #1 \rangle}

$\tuple{a, b, c}$
```

Note that LaTeX macros will not be applied if they occur inside a raw span or block marked with the `raw_attribute` extension.

When `latex_macros` is disabled, the raw LaTeX and math will not have macros applied. This is usually a better approach when you are targeting LaTeX or PDF.

Macro definitions in LaTeX will be passed through as raw LaTeX only if `latex_macros` is not enabled. Macro definitions in Markdown source (or other formats allowing `raw_tex`) will be passed through regardless of whether `latex_macros` is enabled.

## 8.16 Links

Markdown allows links to be specified in several ways.

### 8.16.1 Automatic links

If you enclose a URL or email address in pointy brackets, it will become a link:

```
<https://google.com>
<sam@green.eggs.ham>
```

### 8.16.2 Inline links

An inline link consists of the link text in square brackets, followed by the URL in parentheses. Optionally, the URL can be followed by a link title, in quotes.

```
This is an [inline link](/url), and here's [one with
a title](https://fsf.org "click here for a good time!").
```

There can be no space between the bracketed part and the parenthesized part. The link text can contain formatting (such as emphasis), but the title cannot.

Email addresses in inline links are not autodetected, so they have to be prefixed with `mailto`:

```
[Write me!](mailto:sam@green.eggs.ham)
```

### 8.16.3 Reference links

An _explicit_ reference link has two parts, the link itself and the link definition, which may occur elsewhere in the document (either before or after the link).

The link consists of link text in square brackets, followed by a label in square brackets. (There cannot be space between the two unless the `spaced_reference_links` extension is enabled.) The link definition consists of the bracketed label, followed by a colon and a space, followed by the URL, and optionally (after a space) a link title either in quotes or in parentheses. The label must not be parseable as a citation (assuming the `citations` extension is enabled): citations take precedence over link labels.

Here are some examples:

```
[my label 1]: /foo/bar.html  "My title, optional"
[my label 2]: /foo
[my label 3]: https://fsf.org (The Free Software Foundation)
[my label 4]: /bar#special  'A title in single quotes'
```

The URL may optionally be surrounded by angle brackets:

```
[my label 5]: <http://foo.bar.baz>
```

The title may go on the next line:

```
[my label 3]: https://fsf.org
  "The Free Software Foundation"
```

Note that link labels are not case sensitive. So, this will work:

```
Here is [my link][FOO]

[Foo]: /bar/baz
```

In an _implicit_ reference link, the second pair of brackets is empty:

```
See [my website][].

[my website]: http://foo.bar.baz
```

Note: In `Markdown.pl` and most other Markdown implementations, reference link definitions cannot occur in nested constructions such as list items or block quotes. Pandoc lifts this arbitrary-seeming restriction. So the following is fine in pandoc, though not in most other implementations:

```
> My block [quote].
>
> [quote]: /foo
```

### 8.16.4 Extension: `shortcut_reference_links`

In a _shortcut_ reference link, the second pair of brackets may be omitted entirely:

```
See [my website].

[my website]: http://foo.bar.baz
```

### 8.16.5 Internal links

To link to another section of the same document, use the automatically generated identifier (see Heading identifiers). For example:

```
See the [Introduction](#introduction).
```

or

```
See the [Introduction].

[Introduction]: #introduction
```

Internal links are currently supported for HTML formats (including HTML slide shows and EPUB), LaTeX, and ConTeXt.

## 8.17 Images

A link immediately preceded by a `!` will be treated as an image. The link text will be used as the image's alt text:

```
![la lune](lalune.jpg "Voyage to the moon")

![movie reel]

[movie reel]: movie.gif
```

### 8.17.1 Extension: `implicit_figures`

An image with nonempty alt text, occurring by itself in a paragraph, will be rendered as a figure with a caption. The image's description will be used as the caption.

```
![This is the caption.](image.png)
```

How this is rendered depends on the output format. Some output formats (e.g. RTF) do not yet support figures. In those formats, you'll just get an image in a paragraph by itself, with no caption.

If you just want a regular inline image, just make sure it is not the only thing in the paragraph. One way to do this is to insert a nonbreaking space after the image:

```
![This image won't be a figure](image.png)\
```

Note that in reveal.js slide shows, an image in a paragraph by itself that has the `r-stretch` class will fill the screen, and the caption and figure tags will be omitted.

To specify an alt text for the image that is different from the caption, you can use an explicit attribute (assuming the `link_attributes` extension is set):

```
![The caption.](image.png){alt="description of image"}
```

For LaTeX output, you can specify a figure's positioning by adding the `latex-placement` attribute.

```
![The caption.](image.png){latex-placement="ht"}
```

### 8.17.2 Extension: `link_attributes`

Attributes can be set on links and images:

```
An inline ![image](foo.jpg){#id .class width=30 height=20px}
and a reference ![image][ref] with attributes.

[ref]: foo.jpg "optional title" {#id .class key=val key2="val 2"}
```

(This syntax is compatible with PHP Markdown Extra when only `#id` and `.class` are used.)

For HTML and EPUB, all known HTML5 attributes except `width` and `height` (but including `srcset` and `sizes`) are passed through as is. Unknown attributes are passed through as custom attributes, with `data-` prepended. The other writers ignore attributes that are not specifically supported by their output format.

The `width` and `height` attributes on images are treated specially. When used without a unit, the unit is assumed to be pixels. However, any of the following unit identifiers can be used: `px`, `cm`, `mm`, `in`, `inch` and `%`. There must not be any spaces between the number and the unit. For example:

```
![](file.jpg){ width=50% }
```

- Dimensions may be converted to a form compatible with the output format (for example, dimensions given in pixels will be converted to inches when converting HTML to LaTeX). Conversion between pixels and physical measurements is affected by the `--dpi` option (by default, 96 dpi is assumed, unless the image itself contains dpi information).
- The `%` unit is generally relative to some available space. For example the above example will render to the following.
  - HTML: `<img href="file.jpg" style="width: 50%;" />`
  - LaTeX: `\includegraphics[width=0.5\textwidth,height=\textheight]{file.jpg}` (If you're using a custom template, you need to configure `graphicx` as in the default template.)
  - ConTeXt: `\externalfigure[file.jpg][width=0.5\textwidth]`
- Some output formats have a notion of a class or a unique identifier, or both (HTML).
- When no `width` or `height` attributes are specified, the fallback is to look at the image resolution and the dpi metadata embedded in the image file.

## 8.18 Divs and Spans

Using the `native_divs` and `native_spans` extensions, HTML syntax can be used within Markdown to create native `Div` and `Span` elements in the pandoc AST rather than raw HTML. However, a more elegant syntax is also available.

### 8.18.1 Extension: `fenced_divs`

This extension permits special fenced syntax for native `Div` blocks. A Div begins with a fence containing at least three consecutive colons followed by attributes. The attributes may optionally be followed by another string of consecutive colons.

Note: the `commonmark` parser does not permit colons after the attributes.

The attribute syntax matches that of fenced code blocks. Like fenced code blocks, you can use either attributes in curly braces or a single unbraced word as a class name. The Div closes with another line containing at least three consecutive colons. The fenced Div should be separated by blank lines from adjacent blocks.

Example:

```
::::: {#special .sidebar}
Here is a paragraph.

And another.
:::::
```

Fenced divs can be nested. Opening fences must have attributes:

```
::: Warning ::::::
This is a warning.

::: Danger
This is a warning within a warning.
:::
::::::::::::::::::
```

Fences without attributes always serve as closing fences. Unlike fenced code blocks, the number of colons in the closing fence does not need to match the opening fence. Using fences of different lengths can enhance visual clarity when distinguishing nested divs from parent divs.

### 8.18.2 Extension: `bracketed_spans`

A bracketed sequence of inlines, formatted as one would begin a link, will be treated as a `Span` with attributes when immediately followed by attributes:

```
[This is *some text*]{.class key="val"}
```

## 8.19 Footnotes

### 8.19.1 Extension: `footnotes`

Pandoc's Markdown supports footnotes using this syntax:

```
Here is a footnote reference,[^1] and another.[^longnote]

[^1]: Here is the footnote.

[^longnote]: Here's one with multiple blocks.

    Subsequent paragraphs are indented to show that they
belong to the previous footnote.

        { some.code }

    The whole paragraph can be indented, or just the first
    line.  In this way, multi-paragraph footnotes work like
    multi-paragraph list items.

This paragraph won't be part of the note, because it
isn't indented.
```

Footnote identifiers cannot contain spaces, tabs, newlines, or the characters `^`, `[`, or `]`. These identifiers merely link the reference to the note itself; output displays footnotes with sequential numbering.

Footnotes need not appear at the document's end and may be placed anywhere except within other block elements (lists, block quotes, tables, etc.). Separate each footnote from adjacent content by blank lines.

### 8.19.2 Extension: `inline_notes`

Inline footnotes are permitted, though unlike standard notes, they cannot include multiple paragraphs:

```
Here is an inline note.^[Inline notes are easier to write, since
you don't have to pick an identifier and move down to type the
note.]
```

Inline and regular footnotes can be used together.

## 8.20 Citation syntax

### 8.20.1 Extension: `citations`

To cite a bibliographic item with an identifier foo, use the syntax `@foo`. Normal citations should be included in square brackets, with semicolons separating distinct items:

```
Blah blah [@doe99; @smith2000; @smith2004].
```

How this is rendered depends on the citation style. In an author-date style, it might render as:

```
Blah blah (Doe 1999, Smith 2000, 2004).
```

In a footnote style, it might render as:

```
Blah blah.[^1]

[^1]:  John Doe, "Frogs," *Journal of Amphibians* 44 (1999);
Susan Smith, "Flies," *Journal of Insects* (2000);
Susan Smith, "Bees," *Journal of Insects* (2004).
```

See the [CSL user documentation](https://citationstyles.org/authors/) for more information about CSL styles and how they affect rendering.

Unless a citation key starts with a letter, digit, or `_`, and contains only alphanumerics and single internal punctuation characters (`:.#$%&-+?<>~/`), it must be surrounded by curly braces, which are not considered part of the key. In `@Foo_bar.baz.`, the key is `Foo_bar.baz` because the final period is not *internal* punctuation, so it is not included in the key. In `@{Foo_bar.baz.}`, the key is `Foo_bar.baz.`, including the final period. In `@Foo_bar--baz`, the key is `Foo_bar` because the repeated internal punctuation characters terminate the key. The curly braces are recommended if you use URLs as keys: `[@{https://example.com/bib?name=foobar&date=2000}, p. 33]`.

Citation items may optionally include a prefix, a locator, and a suffix. In:

```
Blah blah [see @doe99, pp. 33-35 and *passim*; @smith04, chap. 1].
```

the first item (`doe99`) has prefix `see`, locator `pp. 33-35`, and suffix `and *passim*`. The second item (`smith04`) has locator `chap. 1` and no prefix or suffix.

Pandoc uses some heuristics to separate the locator from the rest of the subject. It is sensitive to the locator terms defined in the [CSL locale files](https://github.com/citation-style-language/locales). Either abbreviated or unabbreviated forms are accepted. In the `en-US` locale, locator terms can be written in either singular or plural forms, as `book`, `bk.`/`bks.`; `chapter`, `chap.`/`chaps.`; `column`, `col.`/`cols.`; `figure`, `fig.`/`figs.`; `folio`, `fol.`/`fols.`; `number`, `no.`/`nos.`; `line`, `l.`/`ll.`; `note`, `n.`/`nn.`; `opus`, `op.`/`opp.`; `page`, `p.`/`pp.`; `paragraph`, `para.`/`paras.`; `part`, `pt.`/`pts.`; `section`, `sec.`/`secs.`; `sub verbo`, `s.v.`/`s.vv.`; `verse`, `v.`/`vv.`; `volume`, `vol.`/`vols.`; `[U+00B6]`/`[U+00B6][U+00B6]`; `[U+00A7]`/`[U+00A7][U+00A7]`. If no locator term is used, "page" is assumed.

In complex cases, you can force something to be treated as a locator by enclosing it in curly braces or prevent parsing the suffix as locator by prepending curly braces:

```
[@smith{ii, A, D-Z}, with a suffix]
[@smith, {pp. iv, vi-xi, (xv)-(xvii)} with suffix here]
[@smith{}, 99 years later]
```

A minus sign (`-`) before the `@` will suppress mention of the author in the citation. This can be useful when the author is already mentioned in the text:

```
Smith says blah [-@smith04].
```

You can also write an author-in-text citation, by omitting the square brackets:

```
@smith04 says blah.

@smith04 [p. 33] says blah.
```

This will cause the author's name to be rendered, followed by the bibliographical details. Use this form when you want to make the citation the subject of a sentence.

When you are using a note style, it is usually better to let citeproc create the footnotes from citations rather than writing an explicit note. If you do write an explicit note that contains a citation, note that normal citations will be put in parentheses, while author-in-text citations will not. For this reason, it is sometimes preferable to use the author-in-text style inside notes when using a note style.

Many CSL styles will format citations differently when the same source has been cited earlier. In documents with chapters, it is usually desirable to reset this position information at the beginning of every chapter. To do this, add the class `reset-citation-positions` to the heading for each chapter:

```
# The Beginning {.reset-citation-positions}
```

Note that this class only has an effect when placed on top-level headings; it is ignored in nested blocks.

## 8.21 Non-default extensions

The following Markdown syntax extensions are not enabled by default in pandoc, but may be enabled by adding `+EXTENSION` to the format name. For example, `markdown+hard_line_breaks` is Markdown with hard line breaks.

### 8.21.1 Extension: `rebase_relative_paths`

Rewrites relative paths for Markdown links and images based on the path of the file containing the link or image. Pandoc computes the directory of the containing file relative to the working directory and prepends the resulting path to the link or image path.

Example usage:

```
pandoc chap*/*.md -f markdown+rebase_relative_paths
```

Absolute paths, URLs, empty paths, and fragment-only paths are not changed. Relative paths in reference links and images are rewritten relative to the file containing the link reference definition.

### 8.21.2 Extension: `mark`

Highlights text by surrounding it with `==`:

```
This ==is highlighted text.==
```

### 8.21.3 Extension: `attributes`

Allows attributes to be attached to inline or block-level elements when parsing `commonmark`. Uses the same syntax as `header_attributes`.

- Attributes immediately after inline elements affect that element
- Attributes before block elements on their own line affect that element
- Consecutive attribute specifiers may be combined
- Attributes at the end of Setext or ATX headings affect the heading
- Attributes after opening fences in code blocks affect the code block
- Attributes at end of reference link definitions affect referring links

Note: A Span or Div container will be added if needed since pandoc's AST doesn't allow arbitrary element attributes.

### 8.21.4 Extension: `old_dashes`

Selects pandoc <= 1.8.2.1 behavior for parsing smart dashes: `-` before a numeral becomes an en-dash, and `--` becomes an em-dash. Only affects parsing when `smart` is enabled. Automatically selected for `textile` input.

### 8.21.5 Extension: `angle_brackets_escapable`

Allows `<` and `>` to be backslash-escaped, as in GitHub flavored Markdown. Implied by pandoc's default `all_symbols_escapable`.

### 8.21.6 Extension: `lists_without_preceding_blankline`

Allows a list to occur immediately after a paragraph with no intervening blank space.

### 8.21.7 Extension: `four_space_rule`

Selects pandoc <= 2.0 behavior for parsing lists, requiring four spaces indent for list item continuation paragraphs.

### 8.21.8 Extension: `spaced_reference_links`

Allows whitespace between the two components of a reference link:

```
[foo] [bar].
```

### 8.21.9 Extension: `hard_line_breaks`

Interprets all newlines within a paragraph as hard line breaks instead of spaces.

### 8.21.10 Extension: `ignore_line_breaks`

Causes newlines within a paragraph to be ignored rather than treated as spaces or hard line breaks. Intended for use with East Asian languages where spaces aren't used between words.

### 8.21.11 Extension: `east_asian_line_breaks`

Ignores newlines within a paragraph when they occur between two East Asian wide characters. Preferred over `ignore_line_breaks` for mixed text.

### 8.21.12 Extension: `emoji`

Parses textual emojis like `:smile:` as Unicode emoticons.

### 8.21.13 Extension: `tex_math_gfm`

Supports GitHub-specific math formats.

Inline math: `` $`e=mc^2`$ ``

Display math:

    ``` math
    e=mc^2
    ```

### 8.21.14 Extension: `tex_math_single_backslash`

Interprets anything between `\(` and `\)` as inline TeX math, and anything between `\[` and `\]` as display TeX math. Note: This precludes escaping `(` and `[`.

### 8.21.15 Extension: `tex_math_double_backslash`

Interprets anything between `\\(` and `\\)` as inline TeX math, and anything between `\\[` and `\\]` as display TeX math.

### 8.21.16 Extension: `markdown_attribute`

Changes default behavior so Markdown is only parsed inside block-level tags if they have the attribute `markdown=1`. By default, pandoc interprets material inside block-level tags as Markdown.

### 8.21.17 Extension: `mmd_title_block`

Enables MultiMarkdown style title blocks at the top of documents:

```
Title:   My title
Author:  John Doe
Date:    September 1, 2008
Comment: This is a sample mmd title block, with
         a field spanning multiple lines.
```

If `pandoc_title_block` or `yaml_metadata_block` is enabled, they take precedence.

### 8.21.18 Extension: `abbreviations`

Parses PHP Markdown Extra abbreviation keys:

```
*[HTML]: Hypertext Markup Language
```

Abbreviation keys are skipped since pandoc's document model doesn't support abbreviations.

### 8.21.19 Extension: `alerts`

Supports GitHub-style Markdown alerts:

```
> [!TIP]
> Helpful advice for doing things better or more easily.
```

### 8.21.20 Extension: `autolink_bare_uris`

Makes all absolute URIs into links, even without surrounding pointy braces `<...>`.

### 8.21.21 Extension: `mmd_link_attributes`

Parses MultiMarkdown-style key-value attributes on link and image references:

```
This is a reference ![image][ref] with MultiMarkdown attributes.

[ref]: https://path.to/image "Image title" width=20px height=30px
       id=myId class="myClass1 myClass2"
```

### 8.21.22 Extension: `mmd_header_identifiers`

Parses MultiMarkdown-style heading identifiers in square brackets after the heading and before trailing `#`s in ATX headings.

### 8.21.23 Extension: `gutenberg`

Uses Project Gutenberg conventions for `plain` output: all-caps for strong emphasis, underscores for regular emphasis, and extra blank space around headings.

### 8.21.24 Extension: `sourcepos`

Includes source position attributes when parsing `commonmark`. Elements accepting attributes get a `data-pos` attribute; others are placed in surrounding Div or Span elements with `data-pos`.

### 8.21.25 Extension: `short_subsuperscripts`

Parses MultiMarkdown-style subscripts and superscripts starting with `~` or `^`:

```
x^2 = 4
```

or

```
Oxygen is O~2.
```

### 8.21.26 Extension: `wikilinks_title_after_pipe`

Pandoc supports multiple wikilink syntaxes regardless of title position.

Using `--from=markdown+wikilinks_title_after_pipe`:

```
[[URL|title]]
```

Using `--from=markdown+wikilinks_title_before_pipe`:

```
[[title|URL]]
```

## 8.22 Markdown variants

In addition to pandoc's extended Markdown, the following Markdown variants are supported:

- `markdown_phpextra` (PHP Markdown Extra)
- `markdown_github` (deprecated GitHub-Flavored Markdown)
- `markdown_mmd` (MultiMarkdown)
- `markdown_strict` (Markdown.pl)
- `commonmark` (CommonMark)
- `gfm` (Github-Flavored Markdown)
- `commonmark_x` (CommonMark with many pandoc extensions)

To see which extensions are supported for a given format, and which are enabled by default, you can use the command:

```
pandoc --list-extensions=FORMAT
```

where `FORMAT` is replaced with the name of the format.

Note that the list of extensions for `commonmark`, `gfm`, and `commonmark_x` are defined relative to default commonmark. So, for example, `backtick_code_blocks` does not appear as an extension, since it is enabled by default and cannot be disabled.
