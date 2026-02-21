# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Windows-only CLI tool for managing CFV (Checksum File Value) `.sha1` checksum files across directory hierarchies. It wraps the external `cfv.bat` Windows utility (`C:\Windows\cfv.bat`, from [cfv.sourceforge.net](https://cfv.sourceforge.net/)) to check, generate, and verify SHA1 checksums per sub-directory.

## Running the Tool

This project uses `uv` for dependency management and execution (Python >= 3.14 required):

```bash
# Run with uv (inline script metadata handles dependencies automatically)
uv run checksum_file_tool.py --help
uv run checksum_file_tool.py -v D:\Archive check-4-missing-cfv-files
uv run checksum_file_tool.py D:\Archive generate-cfv-files
uv run checksum_file_tool.py D:\Archive verify-cfv-files

# Debug: inspect the Click context object
uv run checksum_file_tool.py D:\Archive check-context-object
```

The script uses PEP 723 inline script metadata (the `# /// script` block at the top), so `uv run` resolves dependencies without a virtual environment.

## Architecture

Single-file CLI (`checksum_file_tool.py`) built with [Click](https://click.palletsprojects.com/):

- **CLI group** (`cli`): Accepts `DIR_PATH` argument (validated via `validate_dir_path`) and `-v/--verbose` flag; stores both in Click's context object (`ctx.obj`) for subcommands.
- **`check-4-missing-cfv-files`**: Scans one level of sub-directories in `DIR_PATH`, checks whether each has a `<subdir>/<subdir>.sha1` file.
- **`generate-cfv-files`**: For sub-directories missing a `.sha1` file, calls `cfv.bat -C -rr -t sha1` (create, recursive, SHA1 type).
- **`verify-cfv-files`**: For all sub-directories, calls `cfv.bat -f <checksum_file>` to verify existing `.sha1` files.

**Key convention**: Each sub-directory's checksum file is named `<subdir_name>.sha1` and lives inside that sub-directory (e.g., `D:\Archive\Movies\Movies.sha1`).

**External dependency**: `C:\Windows\cfv.bat` must be installed separately. This tool will not run on non-Windows systems.

## Constraints

- Windows-only (hardcoded `cfv.bat` path, Windows path conventions).
- Scans only one level deep (direct sub-directories of `DIR_PATH`); not recursive at the top level.
- No test suite currently exists in this repository.
