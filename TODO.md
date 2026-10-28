# TODO — Code Cleanup, Structuring & Security

Identified issues in `checksum_file_tool.py`, sorted by priority. Item IDs are
kept stable; gaps are items that have been completed.

---

## Security Issues

### SEC-1 [HIGH] — Symlink following allows out-of-scope filesystem operations
`os.scandir()` returns entries for symbolic links, and `entry.is_dir()` returns
`True` for a symlink pointing to a directory (it follows the link by default).
This means an attacker who can create a symlink inside `DIR_PATH` could point it
at any directory on the system (e.g. `C:\Windows\System32`). The `generate-cfv-files`
command would then invoke `cfv.bat -C -rr -t sha1` inside that directory, potentially
writing files to sensitive locations.

**Fix:** Use `entry.is_dir(follow_symlinks=False)` to restrict traversal to real
directories only. This applies to `scan_dir` (mode detection) and to the nested-mode
loops in all three commands. It changes documented behaviour (README "Edge cases"
says symlinks and junctions are followed) and can change which mode a layout is
detected as, so update the README and bump the version accordingly.

```python
# Vulnerable:
if entry.is_dir():

# Safe:
if entry.is_dir(follow_symlinks=False):
```

### SEC-2 [HIGH] — Blind trust in a mutable `cfv.bat` path
`run_cfv` checks that `C:\Windows\cfv.bat` exists, but not that it is genuine.
`C:\Windows\cfv.bat` (and the `cfv.exe` it launches) can be replaced by any process
with administrator privileges, and this tool will execute whatever is there without
any verification.

### SEC-3 [HIGH] — TOCTOU race condition on SHA1 file existence checks
`check-4-missing-cfv-files`, `generate-cfv-files`, `verify-cfv-files` and mode
detection (`scan_dir` / `detect_mode`) call `os.path.exists(sha1_checksum_filepath)`
and then act on the result in a separate operation. In between those two steps,
another process could:
- Create a `.sha1` file where none existed (causing the generator to skip it silently)
- Delete or replace a `.sha1` file (causing the checker to misreport its state)
- Swap a legitimate `.sha1` file for a malicious one before cfv.bat reads it

This is a classic Time-of-Check/Time-of-Use (TOCTOU) race. For a single-user
desktop tool the practical risk is low, but it should be acknowledged and, where
possible, mitigated by checking existence as close to the action as possible and
handling the case where the state has changed.

### SEC-5 [MEDIUM] — No timeout on `subprocess.run` calls
`run_cfv` calls `subprocess.run` without a `timeout` argument. If cfv.bat hangs
(e.g. blocked on I/O, waiting on a network path, or encountering a corrupt archive),
the script hangs indefinitely with no way to recover other than killing the process.
In an automated or scheduled context this can cause resource exhaustion.

**Fix:** Pass a sensible `timeout` value and handle `subprocess.TimeoutExpired` by
reporting the directory as failed (returning `False`), so `do_calculate_checksums`
still removes the incomplete checksum file:
```python
result = subprocess.run([CFV_BAT, *args], cwd=dir_path, timeout=300)
```

### SEC-6 [MEDIUM] — Subprocess output is not captured or logged
`run_cfv` calls `subprocess.run` without `capture_output` or `stdout`/`stderr` pipes,
so cfv.bat's output goes directly to the terminal and is never captured by the
script. This has two consequences:
- There is no audit trail of what cfv.bat reported for each directory.
- If cfv.bat outputs sensitive path information or error details on stderr, it
  is displayed without any filtering.

The script also cannot distinguish between different cfv.bat failure modes; it
only sees a non-zero return code.

**Fix:** Capture output and log or display it under the `--verbose` flag:
```python
result = subprocess.run([CFV_BAT, *args], cwd=dir_path,
                        capture_output=True, text=True, timeout=300)
if verbose or result.returncode != 0:
    click.echo(result.stdout)
    if result.stderr:
        click.echo(result.stderr, err=True)
```

### SEC-7 [LOW] — Debug command exposes internal context object
`check-context-object` dumps the complete `ctx.obj` dict to stdout via `pprint`.
Currently `ctx.obj` only holds `dir_path`, `verbose` and `force_mode`, but if the
context is ever extended (e.g. to carry credentials, API tokens, or other sensitive
configuration), this command will leak them verbatim. The command should either be
removed before any production/shared use or guarded by an environment variable /
debug flag.

### SEC-8 [LOW] — No bounds check on `DIR_PATH` in nested mode; a typo can be destructive
Flat mode is refused on a drive root, but nested mode is not. A user typo such as
`D:\` instead of `D:\Archive` is detected as nested when the drive root holds only
directories, and `generate-cfv-files` then invokes cfv.bat recursively inside every
top-level directory on that drive, creating potentially thousands of `.sha1` files.
Consider adding a confirmation prompt (or requiring `--nested`) when `DIR_PATH`
appears unusually broad (e.g. a drive root or a system directory).

### SEC-9 [LOW] — No file locking; concurrent runs can corrupt `.sha1` files
Nothing prevents two instances of the tool from running simultaneously against
the same `DIR_PATH`. If both detect a missing `.sha1` file for the same
sub-directory at the same time, both will invoke `cfv.bat -C` concurrently,
with one likely overwriting the other's partially-written output. The resulting
checksum file could be corrupt or incomplete. If one of the runs fails, its cleanup
in `do_calculate_checksums` could also delete the file the other run just wrote.
A lock file under `DIR_PATH` or a process-level mutex would prevent this.

---

## High Priority (Bugs / Correctness)

### 2. Extract SHA1 filepath construction into a helper
The `<dir>\<dir name>.sha1` path is built inline in many places: the flat and
nested branches of all three commands, `scan_dir`, `detect_mode` and
`do_calculate_checksums`. Extract to a small helper function, e.g.
`get_sha1_path(dir_path)`.

### 3. Replace `assert` with proper runtime guards
The nested branch of `checkForMissingCfvFiles` uses `assert` for production
invariant checks:
```python
assert count_dirs_with_checksums == count_dirs
assert not dirs_without_checksums
```
`assert` is disabled when Python runs with `-O`. Replace with `raise RuntimeError(...)`
or remove — the surrounding logic already guarantees those conditions hold.

---

## Medium Priority (Style / Consistency)

### 6. Rename camelCase functions and variables to snake_case
Python convention is `snake_case` for all functions and local variables. Current
offenders:

| Current name | Should be |
|---|---|
| `checkForMissingCfvFiles` | `check_for_missing_cfv_files` |
| `generateCfvFiles` | `generate_cfv_files` |
| `verifyCfvFiles` | `verify_cfv_files` |
| `checkContext` | `check_context` |
| `dirPath` | `dir_path` |
| `countDirsScanned` | `count_dirs_scanned` |
| `countCfvFilesGenerated` | `count_cfv_files_generated` |
| `countCfvFilesFailed` | `count_cfv_files_failed` |
| `countCfvFilesVerified` | `count_cfv_files_verified` |

### 7. Remove the `do_` prefix from helper functions
`do_calculate_checksums` and `do_verify_checksums` — the `do_` prefix is
non-Pythonic and adds no information. Rename to `calculate_checksums` /
`verify_checksums`, or more descriptively `run_cfv_create` / `run_cfv_verify`.

### 8. Unify `Path` vs `os.path` usage
`pathlib.Path` is imported and used for the CLI argument but the command bodies
fall back to `os.path.join`, `os.path.exists`, and `os.scandir`. Commit to one
approach — `pathlib` throughout is more readable:

```python
# Instead of:
sha1_checksum_filepath = os.path.join(entry.path, entry.name) + SHA1_EXT
if os.path.exists(sha1_checksum_filepath): ...

# Use pathlib:
for subdir in dir_path.iterdir():
    if subdir.is_dir():
        sha1_path = subdir / (subdir.name + SHA1_EXT)
        if sha1_path.exists(): ...
```

### 9. Replace string-keyed `ctx.obj` dict with a dataclass
The context is passed as a plain dict accessed via string constants (`DIR_PATH_ARG`,
`VERBOSE_FLAG`, `FORCE_MODE_ARG`). A dataclass is safer, self-documenting, and gives
IDE autocomplete:

```python
from dataclasses import dataclass

@dataclass
class CliContext:
    dir_path: Path
    verbose: bool
    force_mode: str | None
```

---

## Low Priority (Cleanup / Polish)

### 10. Fix redundant/misleading verbose output in `generate-cfv-files`
The verbose block at the end of the nested branch of `generateCfvFiles` is outside
the `with` block and has two problems:
- When files were generated, it re-prints the count that the summary already printed.
- When no files were generated, it would print "Generated cfv checksums for 0
  directories" — confusing given the message above says nothing was generated.

### 11. Remove manual `Args:` sections from docstrings
The `Args: ctx (_type_): ...` sections in each command's docstring duplicate what
Click already handles separately, and Click prints them in each command's `--help`
output. Keep only the prose description.

### 12. Fix comment typo
In `checkForMissingCfvFiles`, the comment above `dirPath = ctx.obj[DIR_PATH_ARG]`
has the typo "directoryu" (should be "directory"); the full comment is also
redundant given the variable name.

### 13. Move `pprint` import to the one place it is used
`pprint` is only used in the debug `check-context-object` command. Move it to a
local import inside that function rather than cluttering the module-level imports.
