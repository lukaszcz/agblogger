# Running pandoc as a web server

If you rename (or symlink) the pandoc executable to `pandoc-server`, or if you call pandoc with `server` as the first argument, it will start up a web server with a JSON API. This server exposes most of the conversion functionality of pandoc. For full documentation, see the [pandoc-server](https://github.com/jgm/pandoc/blob/master/doc/pandoc-server.md) man page.

If you rename (or symlink) the pandoc executable to `pandoc-server.cgi`, it will function as a CGI program exposing the same API as `pandoc-server`.

`pandoc-server` is designed to be maximally secure; it uses Haskell's type system to provide strong guarantees that no I/O will be performed on the server during pandoc conversions.
