# Custom Readers and Writers

Pandoc can be extended with custom readers and writers written in [Lua](https://www.lua.org). (Pandoc includes a Lua interpreter, so Lua need not be installed separately.)

To use a custom reader or writer, simply specify the path to the Lua script in place of the input or output format. For example:

```
pandoc -t data/sample.lua
pandoc -f my_custom_markup_language.lua -t latex -s
```

If the script is not found relative to the working directory, it will be sought in the `custom` subdirectory of the user data directory (see `--data-dir`).

A custom reader is a Lua script that defines one function, Reader, which takes a string as input and returns a Pandoc AST. See the [Lua filters documentation](https://pandoc.org/lua-filters.html) for documentation of the functions that are available for creating pandoc AST elements. For parsing, the [lpeg](http://www.inf.puc-rio.br/~roberto/lpeg/) parsing library is available by default. To see a sample custom reader:

```
pandoc --print-default-data-file creole.lua
```

If you want your custom reader to have access to reader options (e.g. the tab stop setting), you give your Reader function a second `options` parameter.

A custom writer is a Lua script that defines a function that specifies how to render each element in a Pandoc AST. See the [djot-writer.lua](https://github.com/jgm/djot.lua/blob/main/djot-writer.lua) for a full-featured example.

Note that custom writers have no default template. If you want to use `--standalone` with a custom writer, you will need to specify a template manually using `--template` or add a new default template with the name `default.NAME_OF_CUSTOM_WRITER.lua` to the `templates` subdirectory of your user data directory (see [Templates](https://pandoc.org/MANUAL.html#templates)).
