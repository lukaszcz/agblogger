# Jupyter Notebooks

When creating a [Jupyter notebook](https://nbformat.readthedocs.io/en/latest/), pandoc will try to infer the notebook structure. Code blocks with the class `code` will be taken as code cells, and intervening content will be taken as Markdown cells. Attachments will automatically be created for images in Markdown cells. Metadata will be taken from the `jupyter` metadata field. For example:

```
---
title: My notebook
jupyter:
  nbformat: 4
  nbformat_minor: 5
  kernelspec:
     display_name: Python 2
     language: python
     name: python2
  language_info:
     codemirror_mode:
       name: ipython
       version: 2
     file_extension: ".py"
     mimetype: "text/x-python"
     name: "python"
     nbconvert_exporter: "python"
     pygments_lexer: "ipython2"
     version: "2.7.15"
---

# Lorem ipsum

**Lorem ipsum** dolor sit amet, consectetur adipiscing elit. Nunc luctus
bibendum felis dictum sodales.

``` code
print("hello")
```

## Pyout

``` code
from IPython.display import HTML
HTML("""
<script>
console.log("hello");
</script>
<b>HTML</b>
""")
```

## Image

This image ![image](myimage.png) will be
included as a cell attachment.
```

If you want to add cell attributes, group cells differently, or add output to code cells, then you need to include divs to indicate the structure. You can use either fenced divs or native divs for this. Here is an example:

```
:::::: {.cell .markdown}
# Lorem

**Lorem ipsum** dolor sit amet, consectetur adipiscing elit. Nunc luctus
bibendum felis dictum sodales.
::::::

:::::: {.cell .code execution_count=1}
``` {.python}
print("hello")
```

::: {.output .stream .stdout}
```
hello
```
:::
::::::

:::::: {.cell .code execution_count=2}
``` {.python}
from IPython.display import HTML
HTML("""
<script>
console.log("hello");
</script>
<b>HTML</b>
""")
```

::: {.output .execute_result execution_count=2}
```{=html}
<script>
console.log("hello");
</script>
<b>HTML</b>
hello
```
:::
::::::
```

If you include raw HTML or TeX in an output cell, use the raw attribute, as shown in the last cell of the example above. Although pandoc can process "bare" raw HTML and TeX, "the result is often interspersed raw elements and normal textual elements" and output cells expect a single, connected raw block. To avoid using raw HTML or TeX except when marked explicitly, specify the extensions `-raw_html-raw_tex+raw_attribute` when translating between Markdown and ipynb notebooks.

Note that options and extensions affecting Markdown reading and writing also affect Markdown cells in ipynb notebooks. For example, `--wrap=preserve` preserves soft line breaks in Markdown cells; `--markdown-headings=setext` uses Setext-style headings; and `--preserve-tabs` prevents tabs from being converted to spaces.
