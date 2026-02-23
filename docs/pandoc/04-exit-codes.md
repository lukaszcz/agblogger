# Exit codes

If pandoc completes successfully, it will return exit code 0. Nonzero exit codes have the following meanings:

| Code | Error |
|------|-------|
| 1 | PandocIOError |
| 3 | PandocFailOnWarningError |
| 4 | PandocAppError |
| 5 | PandocTemplateError |
| 6 | PandocOptionError |
| 21 | PandocUnknownReaderError |
| 22 | PandocUnknownWriterError |
| 23 | PandocUnsupportedExtensionError |
| 24 | PandocCiteprocError |
| 25 | PandocBibliographyError |
| 31 | PandocEpubSubdirectoryError |
| 43 | PandocPDFError |
| 44 | PandocXMLError |
| 47 | PandocPDFProgramNotFoundError |
| 61 | PandocHttpError |
| 62 | PandocShouldNeverHappenError |
| 63 | PandocSomeError |
| 64 | PandocParseError |
| 66 | PandocMakePDFError |
| 67 | PandocSyntaxMapError |
| 83 | PandocFilterError |
| 84 | PandocLuaError |
| 89 | PandocNoScriptingEngine |
| 91 | PandocMacroLoop |
| 92 | PandocUTF8DecodingError |
| 93 | PandocIpynbDecodingError |
| 94 | PandocUnsupportedCharsetError |
| 95 | PandocInputNotTextError |
| 97 | PandocCouldNotFindDataFileError |
| 98 | PandocCouldNotFindMetadataFileError |
| 99 | PandocResourceNotFound |
