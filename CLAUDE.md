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

- **CLI group** (`cli`): Accepts `DIR_PATH` argument (validated via `validate_dir_path`), `-v/--verbose`, and `--flat`/`--nested` (force the mode); stores them in Click's context object (`ctx.obj`) for subcommands.
- **Modes**: *flat* = `DIR_PATH` itself is the unit (`DIR_PATH\<name>.sha1`); *nested* = each immediate sub-directory is a unit. Each command calls `resolve_mode(ctx)`, which uses `detect_mode` unless a flag forces the mode. Detection trusts existing `.sha1` files first, then the layout, and errors out (never guesses) when a folder has both files and sub-directories and no checksum files. The rules are documented in README.md — keep them in sync.
- **`check-4-missing-cfv-files`**: Checks whether the unit(s) have their `<name>.sha1` file.
- **`generate-cfv-files`**: For units missing a `.sha1` file, calls `cfv.bat -C -rr -t sha1` (create, recursive, SHA1 type) with the unit as cwd; cfv names the file after the cwd.
- **`verify-cfv-files`**: For the unit(s), calls `cfv.bat -f <checksum_file>` to verify existing `.sha1` files.

**Key convention**: Each unit's checksum file is named `<unit_name>.sha1` and lives inside that unit (e.g., `D:\Archive\Movies\Movies.sha1`, `D:\Release\Release.sha1`).

**External dependency**: `C:\Windows\cfv.bat` must be installed separately. This tool will not run on non-Windows systems.

## Versioning

- Semantic Versioning; the bump rules and what counts as the public interface (commands, options, exit codes, `.sha1` naming, detected mode) are in README.md "Versioning".
- The version lives **only** in `__version__` in `checksum_file_tool.py`. `click.version_option` reads it and `pyproject.toml` declares `dynamic = ["version"]`. Never hard-code the version anywhere else, including docs (use `X.Y.Z` in examples).
- Bumps go in their own commit: `Bump version to X.Y.Z`.
- Releases follow README.md "Releasing a new version" exactly: annotated `vX.Y.Z` tag on the bump commit, GitHub release via `gh release create --verify-tag` with `checksum_file_tool.py` extracted from the tag (checked with `git hash-object`) and its SHA-256 in the notes. Never move/delete a published tag or replace an asset; fix with a PATCH release. Tag, push and release only when explicitly asked.

## Constraints

- Windows-only (hardcoded `cfv.bat` path, Windows path conventions).
- Mode detection and nested mode look only one level deep (direct contents of `DIR_PATH`); cfv itself hashes each unit recursively.
- Error handling is uniform across modes (rules in README.md "Error handling"): use `report_error` / `exit_with_error` / `report_warning`, never raw `sys.exit` or inline `ERROR:` echoes. Per-directory failures in nested mode are reported and the loop continues; the command exits 1 at the end.
- `do_calculate_checksums` deletes the incomplete `.sha1` cfv leaves behind on failure/Ctrl+C — keep this, or later runs treat the partial file as complete.
- `__main__` reconfigures stdout/stderr to UTF-8 (line-buffered) so ✓/❌ don't crash when output is redirected (cp1252 default).
- No test suite currently exists in this repository.
