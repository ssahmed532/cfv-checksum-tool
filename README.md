# cfv-checksum-tool

A Windows CLI tool for managing [CFV](https://cfv.sourceforge.net/) SHA1 checksum files across a directory of sub-directories. It can detect missing checksum files, generate new ones, and verify existing ones — all in bulk.

> **Windows only.** This tool wraps the external `cfv.bat` utility and has only been tested on Windows.

## Prerequisites

- **Python 3.14+** via [uv](https://docs.astral.sh/uv/)
- **CFV for Windows** installed at `C:\Windows\cfv.bat` — download from [cfv.sourceforge.net](https://cfv.sourceforge.net/)

## Usage

Run directly with `uv` — no manual dependency installation needed:

```
uv run checksum_file_tool.py [OPTIONS] DIR_PATH COMMAND
```

`DIR_PATH` is the root directory whose immediate sub-directories will be scanned.

### Options

| Flag | Description |
|------|-------------|
| `-v`, `--verbose` | Show per-directory status during scan |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

### Commands

#### `check-4-missing-cfv-files`

Reports which sub-directories are missing a `.sha1` checksum file.

```
uv run checksum_file_tool.py -v D:\Archive check-4-missing-cfv-files
```

#### `generate-cfv-files`

Generates a `.sha1` checksum file for every sub-directory that doesn't already have one.

```
uv run checksum_file_tool.py D:\Archive generate-cfv-files
```

#### `verify-cfv-files`

Verifies the `.sha1` checksum file in every sub-directory.

```
uv run checksum_file_tool.py D:\Archive verify-cfv-files
```

## How It Works

Each sub-directory under `DIR_PATH` is expected to contain a checksum file named after itself:

```
D:\Archive\
├── Movies\
│   └── Movies.sha1      ← checksum file for Movies\
├── Music\
│   └── Music.sha1       ← checksum file for Music\
└── Books\               ← missing Books.sha1 — flagged by check-4-missing-cfv-files
```

Only the immediate sub-directories of `DIR_PATH` are scanned (not recursive).

## License

MIT
