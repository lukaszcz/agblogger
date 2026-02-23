# Chunked HTML

`pandoc -t chunkedhtml` will produce a zip archive of linked HTML files, one for each section of the original document. Internal links will automatically be adjusted to point to the right place, images linked to under the working directory will be incorporated, and navigation links will be added. In addition, a JSON file `sitemap.json` will be included describing the hierarchical structure of the files.

If an output file without an extension is specified, then it will be interpreted as a directory and the zip archive will be automatically unpacked into it (unless it already exists, in which case an error will be raised). Otherwise a `.zip` file will be produced.

The navigation links can be customized by adjusting the template. By default, a table of contents is included only on the top page. To include it on every page, set the `toc` variable manually.
