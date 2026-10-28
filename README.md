# cfv-checksum-tool

A Windows CLI tool for managing [CFV](https://cfv.sourceforge.net/) SHA1 checksum files. It can detect missing checksum files, generate new ones, and verify existing ones — either for a single folder (e.g. a TV season release) or in bulk for every sub-directory of an archive. It works out which of the two layouts it is looking at by itself.

> **Windows only.** This tool wraps the external `cfv.bat` utility and has only been tested on Windows.

## Prerequisites

- **Python 3.14+** via [uv](https://docs.astral.sh/uv/)
- **CFV for Windows** installed at `C:\Windows\cfv.bat` — download from [cfv.sourceforge.net](https://cfv.sourceforge.net/)

## Usage

Run directly with `uv` — no manual dependency installation needed:

```
uv run checksum_file_tool.py [OPTIONS] DIR_PATH COMMAND
```

`DIR_PATH` is either a single folder to checksum (**flat** mode) or a parent folder whose immediate sub-directories are each checksummed separately (**nested** mode). See [Modes](#modes).

### Options

Options go **before** `DIR_PATH`.

| Flag | Description |
|------|-------------|
| `-v`, `--verbose` | Show per-directory status during scan (nested mode) |
| `--flat` | Treat `DIR_PATH` as one folder with one checksum file; skips auto-detection |
| `--nested` | Give each sub-directory of `DIR_PATH` its own checksum file; skips auto-detection |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

`--flat` and `--nested` can't be combined. Without either, the mode is [detected automatically](#how-the-mode-is-detected).

### Commands

#### `check-4-missing-cfv-files`

Reports whether checksum files are missing. Read-only.

```
uv run checksum_file_tool.py D:\Carrie.2026.S01.1080p.WEB.H264-RGR check-4-missing-cfv-files
uv run checksum_file_tool.py -v D:\Archive check-4-missing-cfv-files
```

#### `generate-cfv-files`

Generates a `.sha1` checksum file for `DIR_PATH` (flat) or for every sub-directory that doesn't already have one (nested). Existing checksum files are never overwritten. If cfv fails for a directory, the incomplete checksum file it leaves behind is deleted (see [Error handling](#error-handling)).

```
uv run checksum_file_tool.py D:\Carrie.2026.S01.1080p.WEB.H264-RGR generate-cfv-files
uv run checksum_file_tool.py D:\Archive generate-cfv-files
```

#### `verify-cfv-files`

Verifies the `.sha1` checksum file of `DIR_PATH` (flat) or of every sub-directory (nested). A directory with no checksum file counts as a failure, because its contents can't be verified.

```
uv run checksum_file_tool.py D:\Carrie.2026.S01.1080p.WEB.H264-RGR verify-cfv-files
uv run checksum_file_tool.py D:\Archive verify-cfv-files
```

## Modes

Both modes use the same naming rule: a folder's checksum file is named after the folder and lives inside it.

### Flat — one folder, one checksum file

`DIR_PATH` itself is the unit. Everything inside it, **including files in nested folders** such as `Subs\`, is listed in one checksum file:

```
D:\Carrie.2026.S01.1080p.WEB.H264-RGR\
├── Carrie.2026.S01.1080p.WEB.H264-RGR.sha1   ← covers every file below
├── Carrie.2026.S01E01.1080p.WEB.H264-RGR.mkv
├── Carrie.2026.S01E02.1080p.WEB.H264-RGR.mkv
└── Subs\
    └── Carrie.2026.S01E01.srt                ← listed as Subs\Carrie.2026.S01E01.srt
```

### Nested — one checksum file per sub-directory

Each immediate sub-directory of `DIR_PATH` is a unit with its own checksum file:

```
D:\Archive\
├── Movies\
│   └── Movies.sha1      ← checksum file for Movies\
├── Music\
│   └── Music.sha1       ← checksum file for Music\
└── Books\               ← missing Books.sha1 — flagged by check-4-missing-cfv-files
```

Only the immediate sub-directories are units, but each unit's checksum file covers everything inside that sub-directory, however deep. Files sitting directly inside `DIR_PATH` (next to `Movies\`, `Music\`, …) are **not covered by any checksum file**; the tool warns about them.

Because the naming rule is shared, a folder checksummed in flat mode is recognised in nested mode later. For example, if `D:\Carrie.2026.S01.1080p.WEB.H264-RGR` is moved into `D:\Archive`, running the tool on `D:\Archive` sees it as already checksummed.

## How the mode is detected

Unless `--flat` or `--nested` is given, the tool looks at what sits **directly** inside `DIR_PATH` and applies these rules in order. The first rule that matches wins:

| # | What is found directly inside `DIR_PATH` | Result |
|---|---|---|
| 1 | Its own `<DIR_PATH name>.sha1` **and** at least one `<sub>\<sub>.sha1` | **Error**: conflicting checksum files (see [conflicting checksum files](#conflicting-checksum-files)) |
| 2 | Its own `<DIR_PATH name>.sha1` | **Flat** — it was checksummed as one folder before |
| 3 | At least one `<sub>\<sub>.sha1` | **Nested** — it's an archive this tool already manages |
| 4 | Nothing (no files, no sub-directories) | **Error**: empty, nothing to do |
| 5 | Files, no sub-directories | **Flat** |
| 6 | Sub-directories, no files | **Nested** |
| 7 | Both files and sub-directories, no checksum files anywhere | **Error**: ambiguous, re-run with `--flat` or `--nested` |

Rules 2 and 3 trust existing checksum files over the layout, so once a folder has been checksummed it is always detected the same way, even if a folder or file is added later.

Detection ignores `desktop.ini` and `Thumbs.db`, which Windows creates on its own. They don't count as files when deciding the mode.

The tool always prints the mode it picked and why, e.g.:

```
Mode: flat (no sub-directories found)
Mode: flat (found Carrie.2026.S01.1080p.WEB.H264-RGR.sha1)
Mode: nested (3 sub-directories already have checksum files)
Mode: nested (forced by --nested)
```

### Why the tool refuses to guess in rule 7

A folder holding both files and sub-directories could be either layout:

- a release with a `Subs\` or `Sample\` folder → should be **flat**;
- an archive with a stray `notes.txt` → should be **nested**.

Guessing wrong in `generate-cfv-files` is costly. Treating a release as nested creates `Subs\Subs.sha1` and never hashes the videos. Treating an archive as flat hashes the whole archive into a single file, which can take hours. So the tool stops and asks you to choose:

```
ERROR: Can't tell how to treat 'D:\Show.S01': it has 2 files and 1 sub-directories, and no checksum files yet. Re-run with:
  --flat    to checksum it as one folder (e.g. a release with a Subs folder)
  --nested  to checksum each sub-directory separately (e.g. an archive)
```

You only need the flag the first time. After `generate-cfv-files` has run, rule 2 or 3 recognises the folder automatically.

## Scenarios

### Single release folder, files only

`D:\Carrie.2026.S01.1080p.WEB.H264-RGR` contains only `.mkv` files.

| Run | Result |
|---|---|
| `check-4-missing-cfv-files` | `Mode: flat (no sub-directories found)` and `❌ checksum file not found` |
| `verify-cfv-files` (before generating) | Error: no checksum file found, run `generate-cfv-files` first. Exit code 1 |
| `generate-cfv-files` | Creates `Carrie.2026.S01.1080p.WEB.H264-RGR.sha1` |
| `generate-cfv-files` (again) | Nothing generated; the folder already has a checksum file |
| `check-4-missing-cfv-files` | `Mode: flat (found ….sha1)` and `✓ checksum file found` |
| `verify-cfv-files` | Passes. Exit code 0 |
| `verify-cfv-files` after a file changed | cfv lists the mismatching file. Error: failed checksum verification. Exit code 1 |

### Release folder with a `Subs\` or `Sample\` folder

`D:\Show.S01` has `.mkv` files and a `Subs\` folder (rule 7).

1. Any command without a flag stops with the "Can't tell how to treat" error.
2. Run `--flat D:\Show.S01 generate-cfv-files` once. One `Show.S01.sha1` is created, covering the videos and `Subs\…` files.
3. From then on, no flag is needed. Rule 2 detects flat mode.

### Archive of folders

`D:\Archive` contains only sub-directories (rule 6), or some sub-directories already have checksum files (rule 3). It works with no flag, exactly as earlier versions of the tool did.

### Archive with loose files

`D:\Archive` contains sub-directories **and** files such as `notes.txt`.

- **No checksum files yet** (rule 7): the tool stops. Run `--nested D:\Archive generate-cfv-files` once.
- **Some sub-directories already have checksum files** (rule 3): nested mode is picked automatically. A warning names how many loose files are not covered:
  ```
  WARNING: 1 files directly inside [D:\Archive] are not covered by any checksum file in nested mode.
  ```
  Move loose files into a sub-directory if they need protecting.

### Folder previously checksummed the wrong way

If an earlier version of this tool was run on a release folder that has a `Subs\` folder, it will have created `Subs\Subs.sha1` and no checksum for the videos. Rule 3 then detects that folder as **nested**. The warning about uncovered files is the sign that this happened. To fix it:

1. Delete `Subs\Subs.sha1`.
2. Run `generate-cfv-files` on the release folder. Add `--flat` if the folder now hits rule 7.

### Conflicting checksum files

A folder has its own `<name>.sha1` **and** a sub-directory has its own `<sub>.sha1` (rule 1), e.g. after it was checksummed in both modes. The tool stops rather than pick one. Delete the checksum files that don't belong, or pass `--flat` / `--nested` to choose explicitly.

### Empty folder

A folder with nothing in it, or only `desktop.ini` / `Thumbs.db` (rule 4), stops with "is empty, there is nothing to do." Forcing `--flat` still runs cfv, which checksums whatever is there, including `desktop.ini`.

### Forcing the wrong mode

The flags override detection completely, so forcing a mode that doesn't match the layout does what you asked:

- `--nested` on a folder with no sub-directories: `check-4-missing-cfv-files` and `generate-cfv-files` report "No sub-directories found … there is nothing to do." (exit code 0). `verify-cfv-files` reports "ERROR: No sub-directories found … there is nothing to verify." (exit code 1), because nothing was verified. The uncovered-files warning is also shown.
- `--flat` on an archive: `generate-cfv-files` hashes the **entire archive** into one `<archive>.sha1`. Only do this deliberately.

## Edge cases

| Case | Behaviour |
|---|---|
| `DIR_PATH` doesn't exist | `ERROR: Directory '…' does not exist.` Exit code 1 |
| `DIR_PATH` is a file | `ERROR: Path '…' is not a directory.` Exit code 1 |
| `DIR_PATH` is a drive root, e.g. `D:\` | Flat mode (forced or detected) is refused: a drive root has no name to build `<name>.sha1` from. Nested mode works as usual |
| `--flat` and `--nested` together | Usage error. Exit code 2 |
| Folder name containing dots, e.g. `Carrie.2026.S01.1080p.WEB.H264-RGR` | Fully supported; the whole name is used, e.g. `Carrie.2026.S01.1080p.WEB.H264-RGR.sha1` |
| `desktop.ini` / `Thumbs.db` | Ignored by detection only. cfv still includes them in the checksum file when generating. If Windows later rewrites `Thumbs.db`, verification reports it as changed |
| Other `.sha1`, `.sfv`, `.nfo` files shipped with a release | Count as ordinary files for detection. They are hashed like any other file |
| Sub-directory that is a symlink or junction | Followed and treated as a normal sub-directory |
| `DIR_PATH` can't be read (e.g. access denied) | `ERROR: Can't read '…': Access is denied`. Exit code 1 |
| A sub-directory can't be read (nested mode) | cfv fails for that sub-directory only; it is reported and the rest still run. Exit code 1 at the end |
| A file is locked or unreadable while generating | cfv fails; the incomplete checksum file is deleted and the failure reported. Exit code 1. Re-run once the file is free |
| `C:\Windows\cfv.bat` not installed | `ERROR: C:\Windows\cfv.bat not found; install CFV from …`. Exit code 1. Nothing is written. `check-4-missing-cfv-files` doesn't need cfv and still works |
| Ctrl+C while generating | The incomplete checksum file for the directory being processed is deleted, then the tool stops with `Aborted!` (exit code 1). Checksum files already completed are kept |
| Command `--help`, e.g. `D:\Show.S01 generate-cfv-files --help` | Shows help even if the folder would be ambiguous; detection only runs when a command actually executes |

## Error handling

The same rules apply in flat and nested mode:

- **Every problem is reported on stderr** as a red `ERROR: …` line. Non-fatal notices are yellow `WARNING: …` lines. Normal progress and summaries go to stdout.
- **Problems that stop everything** end the run immediately with exit code 1: a bad `DIR_PATH`, an unreadable `DIR_PATH`, a detection error, flat mode on a drive root, or a missing `cfv.bat`.
- **Problems with one directory don't stop the others.** In nested mode a failing sub-directory is reported, the remaining sub-directories are still processed, and the run ends with exit code 1. In flat mode there is only one directory, so the run ends with exit code 1 straight away.
- **No incomplete checksum files are left behind.** When cfv fails partway (e.g. a file is locked), it still writes a checksum file listing only the files it could read. If that file were kept, later runs would treat it as complete: `generate-cfv-files` would skip the directory and `verify-cfv-files` would pass it without checking the missing files. The tool deletes it and prints `WARNING: Removed incomplete checksum file …`. If it can't be deleted, an error asks you to delete it by hand. Only a checksum file created by the current run is ever deleted; existing ones are never touched.
- **A missing checksum file is a verification failure,** in both modes: `ERROR: No checksum file found for […]; run generate-cfv-files first.`

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | The command did everything it was asked to do |
| 1 | Something failed: see the `ERROR:` lines. Covers the stop-everything problems above, plus the per-command cases below |
| 2 | Command-line usage error, e.g. `--flat` and `--nested` together, or an unknown command |

| Command | Exit code 1 when … | Exit code 0 includes … |
|---|---|---|
| `check-4-missing-cfv-files` | Only the stop-everything problems | Checksum files are missing; this command only reports |
| `generate-cfv-files` | cfv fails for any directory | Nothing needed generating; no sub-directories found with `--nested` |
| `verify-cfv-files` | Any directory fails verification or has no checksum file; no sub-directories found with `--nested` (nothing was verified) | — |

## Output and logging

Output can be piped or redirected to a log file, e.g. `uv run checksum_file_tool.py D:\Archive verify-cfv-files > verify.log 2>&1`. The tool writes its own lines as UTF-8 when output is redirected, so the ✓ / ❌ marks and non-English folder names in them are logged correctly. cfv's lines are written by cfv itself in its own encoding. The tool's lines and cfv's output stay in order when both streams go to the same file.

In PowerShell, capturing with `2>&1` into a variable or pipeline reads stdout and stderr separately, so `ERROR:` lines may appear a line or two away from where they happened. Redirecting to a file with `> file 2>&1` doesn't have this problem.

## Known limitations

- Only the layout directly inside `DIR_PATH` is used for detection; sub-directories of sub-directories are not inspected.
- cfv's own messages (e.g. `crc does not match`, `Permission denied`, or a cfv traceback when a directory can't be listed) are passed through unchanged.

## License

MIT
