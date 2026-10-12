# Source line ranking (`loc-rank`)

`loc-rank` groups source files by extension and lists each group from fewest to most physical lines. Groups are ordered by their largest file, so the largest file overall appears at the bottom of the terminal. Extensionless scripts use a `script (interpreter)` group based on their shebang. It counts blank lines and comments, including a final line without a newline. Equal counts sort by relative path. `--top N` selects the N largest files across all groups before grouping them.

```bash
loc-rank                    # scan the current directory
loc-rank /path/to/project   # scan another project
loc-rank --top 20           # show the 20 largest files
```

Example output:

```text
[.py]
LINES  FILE
   42  app/routes.py
  120  app/server.py

[.vue]
LINES  FILE
  180  frontend/Dashboard.vue
```

The prototype recognizes common programming and web source extensions, including Python, C/C++, JavaScript, TypeScript, Vue, Rust, Go, Java, shell, HTML, and CSS. Extensionless files with a recognized script shebang are included. Binary files and symlinks are skipped. Hidden directories and common dependency, cache, build, and output directories are skipped; individual hidden source files can be counted. The scan is read-only and does not depend on Git. File read errors are reported and produce a nonzero exit status.

Run it directly with `python3 src/system-utilities/loc-rank/scripts/loc-rank` or install it using `./main.sh setup --module loc-rank`. Remove the installed command with `./main.sh uninstall --module loc-rank`. Python 3.9 or newer is required.

Run `python3 src/system-utilities/loc-rank/tests/LocRankTest.py` for focused tests.
