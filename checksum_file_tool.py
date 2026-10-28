# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "click>=8.1.0",
# ]
# ///
#
# A utility script to scan a given root directory (dir_path) and identify
# those sub-directories that have missing (non-existent) CFV checksum files.
#
# Note:
#   1) This script has only been tested and developed for Windows OSes.
#   2) This script will not work on any other OS/platform.
#   3) This script depends on the external CFV windows utility package (d/l from https://cfv.sourceforge.net/)
#
# Usage with uv:
#   uv run checksum_file_tool.py [OPTIONS] DIR_PATH COMMAND [ARGS]...
#   uv run checksum_file_tool.py --help
#   uv run checksum_file_tool.py -v D:\Archive check-4-missing-cfv-files
#   uv run checksum_file_tool.py D:\Archive generate-cfv-files
#   uv run checksum_file_tool.py D:\Archive verify-cfv-files
#
# Various references for click library usage:
#   - https://www.assemblyai.com/blog/the-definitive-guide-to-python-click/
#   - https://realpython.com/python-click/
#   - https://www.codium.ai/blog/building-user-friendly-python-command-line-interfaces-with-click-and-command-line/
#

import os
import pprint
import subprocess
import sys
from pathlib import Path

import click

CFV_BAT = "C:\\Windows\\cfv.bat"
DIR_PATH_ARG = "dir_path"
SHA1_EXT = ".sha1"
VERBOSE_FLAG = "verbose"
FORCE_MODE_ARG = "force_mode"
MODE_FLAT = "flat"
MODE_NESTED = "nested"
# Windows creates these by itself; they say nothing about how a directory is
# laid out, so mode detection ignores them.
IGNORED_FILES = {"desktop.ini", "thumbs.db"}


def report_error(message):
    click.echo(click.style(f"ERROR: {message}", fg="red", bold=True), err=True)


def exit_with_error(message):
    report_error(message)
    sys.exit(1)


def report_warning(message):
    click.echo(click.style(f"WARNING: {message}", fg="yellow"), err=True)


def validate_dir_path(ctx, param, value):
    """Custom validator for directory path with styled error messages.

    Args:
        ctx: Click context object
        param: Click parameter object
        value: Path value to validate

    Returns:
        Path: The validated directory path
    """
    if not value.exists():
        exit_with_error(f"Directory '{value}' does not exist.")

    if not value.is_dir():
        exit_with_error(f"Path '{value}' is not a directory.")

    return value


def run_cfv(args, dir_path) -> bool:
    """Run cfv.bat with dir_path as the working directory.

    Exits if cfv.bat isn't installed, since no command can succeed without it.
    Any other failure to start it (e.g. dir_path is unreadable) only fails this
    one directory, so the remaining sub-directories in nested mode still run.
    """
    if not os.path.isfile(CFV_BAT):
        exit_with_error(f"{CFV_BAT} not found; install CFV from https://cfv.sourceforge.net/")
    try:
        result = subprocess.run([CFV_BAT, *args], cwd=dir_path)
    except OSError as e:
        report_error(f"Could not run cfv in [{dir_path}]: {e}")
        return False
    return result.returncode == 0


def do_calculate_checksums(dir_path) -> bool:
    """Create <dir_path>\\<dir name>.sha1. Callers only call this when that file
    doesn't exist yet, so any file there afterwards was written by this run.

    When cfv fails (e.g. a file is locked) or is interrupted with Ctrl+C, it
    leaves behind an incomplete checksum file listing only the files it could
    read. That file is deleted, otherwise later runs would treat it as complete:
    generate would skip the directory and verify would pass it while never
    checking the missing files.
    """
    sha1_checksum_filepath = os.path.join(dir_path, os.path.basename(dir_path)) + SHA1_EXT
    succeeded = False
    try:
        succeeded = run_cfv(["-C", "-rr", "-t", "sha1"], dir_path)
    finally:
        if not succeeded and os.path.exists(sha1_checksum_filepath):
            try:
                os.remove(sha1_checksum_filepath)
                report_warning(f"Removed incomplete checksum file {sha1_checksum_filepath}")
            except OSError as e:
                report_error(
                    f"Could not remove incomplete checksum file {sha1_checksum_filepath} "
                    f"({e.strerror}); delete it before re-running generate-cfv-files."
                )
    return succeeded


def do_verify_checksums(dir_path, checksum_file) -> bool:
    return run_cfv(["-f", checksum_file], dir_path)


def scan_dir(dir_path):
    """Count what sits directly inside dir_path.

    Returns:
        tuple: (# of sub-directories, # of those that have their own
                <subdir>.sha1 file, # of files other than IGNORED_FILES)
    """
    count_subdirs = 0
    count_subdirs_with_checksums = 0
    count_files = 0
    try:
        with os.scandir(dir_path) as entries:
            for entry in entries:
                if entry.is_dir():
                    count_subdirs += 1
                    if os.path.exists(os.path.join(entry.path, entry.name) + SHA1_EXT):
                        count_subdirs_with_checksums += 1
                elif entry.name.lower() not in IGNORED_FILES:
                    count_files += 1
    except OSError as e:
        exit_with_error(f"Can't read '{dir_path}': {e.strerror}")
    return count_subdirs, count_subdirs_with_checksums, count_files


def detect_mode(dir_path, count_subdirs, count_subdirs_with_checksums, count_files):
    """Decide whether dir_path is a single checksum unit (flat) or a parent of
    checksum units (nested). Existing checksum files are trusted first, then the
    layout. Exits with an error rather than guess when the layout is ambiguous,
    because a wrong guess in generate-cfv-files silently produces the wrong
    checksum files.

    Returns:
        tuple: (mode, human readable reason)
    """
    # a drive root has no name, so it can never hold a flat <name>.sha1 file
    has_flat_checksum = bool(dir_path.name) and os.path.exists(
        os.path.join(dir_path, dir_path.name) + SHA1_EXT
    )

    if has_flat_checksum and count_subdirs_with_checksums:
        exit_with_error(
            f"'{dir_path}' has its own {dir_path.name}{SHA1_EXT} file and "
            f"{count_subdirs_with_checksums} sub-directories have their own "
            f"checksum files too, so it is unclear how it should be treated. "
            f"Remove the checksum files that don't belong, or re-run with "
            f"--flat or --nested."
        )
    if has_flat_checksum:
        return MODE_FLAT, f"found {dir_path.name}{SHA1_EXT}"
    if count_subdirs_with_checksums:
        return MODE_NESTED, (
            f"{count_subdirs_with_checksums} sub-directories already have checksum files"
        )
    if count_subdirs == 0 and count_files == 0:
        exit_with_error(f"'{dir_path}' is empty, there is nothing to do.")
    if count_subdirs == 0:
        return MODE_FLAT, "no sub-directories found"
    if count_files == 0:
        return MODE_NESTED, "only sub-directories found"
    exit_with_error(
        f"Can't tell how to treat '{dir_path}': it has {count_files} files and "
        f"{count_subdirs} sub-directories, and no checksum files yet. Re-run with:\n"
        f"  --flat    to checksum it as one folder (e.g. a release with a Subs folder)\n"
        f"  --nested  to checksum each sub-directory separately (e.g. an archive)"
    )


def resolve_mode(ctx):
    """Return the mode to run in (forced by --flat/--nested, or detected)
    and tell the user which one was picked and why."""
    dirPath = ctx.obj[DIR_PATH_ARG]
    count_subdirs, count_subdirs_with_checksums, count_files = scan_dir(dirPath)

    mode = ctx.obj[FORCE_MODE_ARG]
    if mode:
        reason = f"forced by --{mode}"
    else:
        mode, reason = detect_mode(
            dirPath, count_subdirs, count_subdirs_with_checksums, count_files
        )

    if mode == MODE_FLAT and not dirPath.name:
        exit_with_error(f"'{dirPath}' is a drive root and can't be checksummed as one folder.")

    click.echo(click.style(f"Mode: {mode} ({reason})", fg="cyan"))
    if mode == MODE_NESTED and count_files:
        report_warning(
            f"{count_files} files directly inside [{dirPath}] are not "
            f"covered by any checksum file in nested mode."
        )
    return mode


@click.group()
@click.pass_context
@click.version_option("0.2.0", prog_name="checksum_file_tool")
@click.option("-v", "--verbose", is_flag=True, help="Display verbose output")
@click.option(
    "--flat",
    is_flag=True,
    help="Treat DIR_PATH as one folder with one checksum file (skips auto-detection)",
)
@click.option(
    "--nested",
    is_flag=True,
    help="Give each sub-directory of DIR_PATH its own checksum file (skips auto-detection)",
)
@click.argument(
    "dir_path",
    type=click.Path(resolve_path=True, path_type=Path),
    callback=validate_dir_path,
)
def cli(ctx, dir_path, verbose, flat, nested):
    if flat and nested:
        raise click.UsageError("--flat and --nested can't be used together.")
    ctx.ensure_object(dict)
    ctx.obj[DIR_PATH_ARG] = dir_path
    ctx.obj[VERBOSE_FLAG] = verbose
    ctx.obj[FORCE_MODE_ARG] = MODE_FLAT if flat else MODE_NESTED if nested else None


@cli.command("check-context-object")
@click.pass_context
def checkContext(ctx):
    pprint.pprint(type(ctx.obj))
    pprint.pprint(ctx.obj)


@cli.command("check-4-missing-cfv-files")
@click.pass_context
def checkForMissingCfvFiles(ctx):
    """Check for missing checksum files (cfv format) in the
       specified directory (flat) or its sub-directories (nested).

    Args:
        ctx (_type_): context object that contains context info & data
    """

    # retrieve the dir_path argument from the context object
    # this is the directoryu path within which to start checking for
    # missing CFV format files
    dirPath = ctx.obj[DIR_PATH_ARG]
    verbose = ctx.obj[VERBOSE_FLAG]

    if resolve_mode(ctx) == MODE_FLAT:
        sha1_checksum_filepath = os.path.join(dirPath, dirPath.name) + SHA1_EXT
        click.echo()
        if os.path.exists(sha1_checksum_filepath):
            click.echo(
                click.style(
                    f"\N{check mark} checksum file found for [{dirPath.name}]",
                    fg="green",
                    bold=True,
                )
            )
        else:
            click.echo(
                click.style(
                    f"\N{cross mark} checksum file not found for [{dirPath.name}]",
                    fg="red",
                    bold=True,
                )
            )
        return

    dirs_without_checksums = []
    count_dirs_with_checksums = 0
    count_dirs_without_checksums = 0
    count_dirs = 0

    with os.scandir(dirPath) as entries:
        for entry in entries:
            if entry.is_dir():
                count_dirs += 1
                sha1_checksum_filepath = os.path.join(entry.path, entry.name) + SHA1_EXT
                if os.path.exists(sha1_checksum_filepath):
                    if verbose:
                        click.echo(
                            click.style(
                                f"\N{check mark} checksum file found for [{entry.name}]",
                                fg="green",
                                bold=True,)
                        )
                    count_dirs_with_checksums += 1
                else:
                    if verbose:
                        click.echo(
                            click.style(
                                f"\N{cross mark} checksum file not found for [{entry.name}]",
                                fg="red",
                                bold=True,
                            )
                        )
                    count_dirs_without_checksums += 1
                    dirs_without_checksums.append(entry.path)

    click.echo()
    if count_dirs == 0:
        click.echo(f"No sub-directories found in [{dirPath}], there is nothing to do.")
    else:
        click.echo(f"# of directories with CFV files: {count_dirs_with_checksums}")
        click.echo(f"# of directories without CFV files: {count_dirs_without_checksums}")
        click.echo()

        if count_dirs_without_checksums == 0:
            assert count_dirs_with_checksums == count_dirs
            assert not dirs_without_checksums
            click.echo(
                click.style(
                    "All checksums appear to be up-to-date: you are all set!",
                    fg="green",
                )
            )


@cli.command("generate-cfv-files")
@click.pass_context
def generateCfvFiles(ctx):
    """Generate a (cfv format) checksum file for the specified directory
       (flat) or for each of its sub-directories (nested).

    Args:
        ctx (_type_): context object that contains context info & data
    """
    dirPath = ctx.obj[DIR_PATH_ARG]
    verbose = ctx.obj[VERBOSE_FLAG]

    if resolve_mode(ctx) == MODE_FLAT:
        sha1_checksum_filepath = os.path.join(dirPath, dirPath.name) + SHA1_EXT
        if os.path.exists(sha1_checksum_filepath):
            click.echo(
                click.style(
                    f"No cfv file generated; [{dirPath.name}] already has a checksum file",
                    fg="green",
                )
            )
            return
        click.echo(f"Generating cfv checksum file for {dirPath} ...")
        if not do_calculate_checksums(dirPath):
            exit_with_error(f"cfv failed to generate a checksum file for [{dirPath.name}]")
        click.echo(
            click.style(f"Generated cfv checksum file {sha1_checksum_filepath}", fg="green")
        )
        return

    countCfvFilesGenerated = 0
    countCfvFilesFailed = 0
    countDirsScanned = 0

    with os.scandir(dirPath) as entries:
        for entry in entries:
            if entry.is_dir():
                countDirsScanned += 1
                sha1_checksum_filepath = os.path.join(entry.path, entry.name) + SHA1_EXT
                if not os.path.exists(sha1_checksum_filepath):
                    click.echo(f"Generating cfv checksum file for {entry.path} ...")
                    if do_calculate_checksums(entry.path):
                        countCfvFilesGenerated += 1
                    else:
                        # keep going so one bad directory doesn't block the rest
                        report_error(f"cfv failed to generate a checksum file for [{entry.name}]")
                        countCfvFilesFailed += 1

        if countCfvFilesGenerated > 0:
            click.echo(
                click.style(
                    f"Generated cfv checksums for {countCfvFilesGenerated} directories",
                    fg="green",
                )
            )
        elif countDirsScanned == 0:
            click.echo(f"No sub-directories found in [{dirPath}], there is nothing to do.")
        elif countCfvFilesFailed == 0:
            click.echo(
                click.style(
                    "No cfv files generated; all sub-directories appear to be up-to-date",
                    fg="green",
                )
            )

    if verbose:
        click.echo(f"Total sub-directories scanned: {countDirsScanned}")
        click.echo(f"Generated cfv checksums for {countCfvFilesGenerated} directories")

    if countCfvFilesFailed:
        exit_with_error(f"Failed to generate cfv checksums for {countCfvFilesFailed} directories")


@cli.command("verify-cfv-files")
@click.pass_context
def verifyCfvFiles(ctx):
    """Verify the (cfv format) checksum file of the specified directory
       (flat) or of each of its sub-directories (nested).

    Args:
        ctx (_type_): context object that contains context info & data
    """
    dirPath = ctx.obj[DIR_PATH_ARG]

    if resolve_mode(ctx) == MODE_FLAT:
        sha1_checksum_filepath = os.path.join(dirPath, dirPath.name) + SHA1_EXT
        if not os.path.exists(sha1_checksum_filepath):
            exit_with_error(
                f"No checksum file found for [{dirPath.name}]; run generate-cfv-files first."
            )
        click.echo(f"Verifying CFV checksum file in {dirPath} ...")
        if not do_verify_checksums(dirPath, sha1_checksum_filepath):
            exit_with_error(f"[{dirPath.name}] failed checksum verification.")
        click.echo(
            click.style(
                f"[{dirPath.name}] successfully passed checksum verification.",
                fg="green",
                bold=True,
            )
        )
        return

    countDirsScanned = 0
    countCfvFilesVerified = 0

    with os.scandir(dirPath) as entries:
        for entry in entries:
            if entry.is_dir():
                countDirsScanned += 1
                sha1_checksum_filepath = os.path.join(entry.path, entry.name) + SHA1_EXT
                if not os.path.exists(sha1_checksum_filepath):
                    report_error(
                        f"No checksum file found for [{entry.name}]; run generate-cfv-files first."
                    )
                    continue
                click.echo(f"Verifying CFV checksum file in {entry.path} ...")
                if do_verify_checksums(entry.path, sha1_checksum_filepath):
                    countCfvFilesVerified += 1
                else:
                    report_error(f"[{entry.name}] failed checksum verification.")

    if countDirsScanned == 0:
        exit_with_error(f"No sub-directories found in [{dirPath}], there is nothing to verify.")

    if countCfvFilesVerified == countDirsScanned:
        click.echo(
            click.style(
                f"{countCfvFilesVerified} out of {countDirsScanned} sub-directories "
                f"successfully passed detailed verification and checksum verification.",
                fg="green",
                bold=True,
            )
        )
    elif countCfvFilesVerified == 0:
        click.echo(
            click.style(
                f"0 out of {countDirsScanned} sub-directories "
                f"passed checksum verification. All directories failed.",
                fg="red",
                bold=True,
            )
        )
    else:
        countFailed = countDirsScanned - countCfvFilesVerified
        click.echo(
            click.style(
                f"{countCfvFilesVerified} out of {countDirsScanned} sub-directories "
                f"passed checksum verification; {countFailed} failed.",
                fg="yellow",
                bold=True,
            )
        )

    if countCfvFilesVerified < countDirsScanned:
        sys.exit(1)


if __name__ == "__main__":
    # When output is piped or redirected, Python encodes it with the ANSI code
    # page (cp1252), which can't encode the check/cross marks and crashes. A real
    # console is unaffected because click writes to it via the Windows console API.
    # Line buffering keeps stdout in order with stderr and cfv's own output,
    # which would otherwise be interleaved out of order in a redirected log.
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8")
    cli()
