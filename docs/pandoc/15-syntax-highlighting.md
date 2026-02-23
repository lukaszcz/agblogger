# Syntax Highlighting

Pandoc automatically highlights syntax in fenced code blocks marked with a language name using the Haskell library skylighting. Highlighting is currently supported for HTML, EPUB, Docx, Ms, Man, Typst, and LaTeX/PDF output formats.

To view available language names, run:

```
pandoc --list-highlight-languages
```

The color scheme is selected using the `--syntax-highlighting` option. The default is `pygments`, which imitates the Python pygments library's color scheme. View available styles with:

```
pandoc --list-highlight-styles
```

To create a custom theme, generate a JSON file from an existing style:

```
pandoc -o my.theme --print-highlight-style pygments
```

Edit `my.theme` and use it:

```
pandoc --syntax-highlighting my.theme
```

Ensure the JSON file uses UTF-8 encoding without a Byte-Order Mark (BOM).

For unsupported languages or custom highlighting, use the `--syntax-definition` option with a KDE-style XML syntax definition file. See KDE's syntax definition repository before creating custom definitions.

Use `--syntax-highlighting=none` to disable highlighting entirely.

The `--syntax-highlighting=idiomatic` option uses format-specific highlighting:

- **reveal.js**: Uses reveal.js's highlighting plugin; customize with `highlightjs-theme` variable
- **Typst**: Uses Typst's built-in highlighting (also the default)
- **LaTeX**: Uses the `listings` package (note: doesn't support multi-byte encoding for UTF-8)
- **Other formats**: Same result as default
