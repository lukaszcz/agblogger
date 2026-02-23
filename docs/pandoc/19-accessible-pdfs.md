# Accessible PDFs and PDF archiving standards

PDF is a flexible format, and using PDF in certain contexts requires additional conventions. For example, PDFs are not accessible by default; they define how characters are placed on a page but do not contain semantic information on the content. However, it is possible to generate accessible PDFs, which use tagging to add semantic information to the document.

Pandoc defaults to LaTeX to generate PDF. LaTeX's `\DocumentMetadata` interface supports PDF standards and tagging when using LuaLaTeX; set the `pdfstandard` variable to enable this (see below). For older LaTeX installations, alternative engines must be used.

The PDF standards PDF/A and PDF/UA define further restrictions intended to optimize PDFs for archiving and accessibility. Tagging is commonly used in combination with these standards to ensure best results.

Note, however, that standard compliance depends on many things, including the colorspace of embedded images. Pandoc cannot check this, and external programs must be used to ensure that generated PDFs are in compliance.

## LaTeX

Set the `pdfstandard` variable to produce tagged PDFs conforming to PDF/A, PDF/X, or PDF/UA standards. For example:

```
pandoc -V pdfstandard=ua-2 --pdf-engine=lualatex doc.md -o doc.pdf
```

Multiple standards can be combined:

```yaml
---
pdfstandard:
  - ua-2
  - a-4f
---
```

The required PDF version is inferred automatically. This feature requires LuaLaTeX in TeX Live 2025 with LaTeX kernel 2025-06-01 or newer.

## ConTeXt

ConTeXt automatically generates tagged PDFs, though output quality depends on source material. By default, pandoc's ConTeXt markup prioritizes readability and reuse over tagging purposes. To optimize for tagging, enable the `tagging` format extension:

```
pandoc -t context+tagging doc.md -o doc.pdf
```

The system requires a recent ConTeXt installation, as earlier versions had a flaw producing invalid PDF metadata.

## WeasyPrint

The HTML-based engine WeasyPrint offers experimental support for PDF/A and PDF/UA beginning with version 57. Tagged PDFs can be generated using:

```
pandoc --pdf-engine=weasyprint \
       --pdf-engine-opt=--pdf-variant=pdf/ua-1 ...
```

The feature is experimental and standard compliance should not be assumed.

## Prince XML

Prince is a commercial HTML-to-PDF conversion tool that offers comprehensive support for different PDF standards and tagging capabilities.

To use Prince with Pandoc, employ the following command structure:

```
pandoc --pdf-engine=prince \
       --pdf-engine-opt=--tagged-pdf ...
```

The `--tagged-pdf` option enables PDF tagging functionality for enhanced document structure and accessibility.

For comprehensive details about Prince's capabilities and configuration options, consult the official Prince documentation.

## Typst

Typst 0.12 can produce PDF/A-2b:

```
pandoc --pdf-engine=typst --pdf-engine-opt=--pdf-standard=a-2b ...
```

## Word processors

Word processors such as LibreOffice and MS Word can generate standardized and tagged PDF output. While Pandoc doesn't directly convert through these applications, it can create `docx` or `odt` files that users can then open and convert to PDF using the appropriate word processor. For instructions, consult the official guides for [Word](https://support.microsoft.com/en-us/office/create-accessible-pdfs-064625e0-56ea-4e16-ad71-3aa33bb4b7ed) and [LibreOffice](https://help.libreoffice.org/latest/en-US/text/shared/01/ref_pdf_export_general.html).
