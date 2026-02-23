# Reproducible builds

Some document formats that pandoc targets (such as EPUB, docx, and ODT) include build timestamps in generated documents. This means successive builds will produce different files even when source material remains unchanged.

To prevent this variation, set the `SOURCE_DATE_EPOCH` environment variable. The timestamp will then derive from this variable rather than the current system time. This variable should contain an integer unix timestamp representing seconds since midnight UTC on January 1, 1970.

For reproducible LaTeX builds, you can specify the `pdf-trailer-id` in metadata. Alternatively, leave it undefined and pandoc will generate a trailer-id based on a hash of the `SOURCE_DATE_EPOCH` and document contents.

Certain document formats include unique identifiers. For EPUB files, you can explicitly set this by defining the `identifier` metadata field (see [EPUB Metadata](11.1-epub-metadata.html#epub-metadata)).
