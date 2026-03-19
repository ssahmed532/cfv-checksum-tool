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

DIR_PATH_ARG = "dir_path"
SHA1_EXT = ".sha1"
VERBOSE_FLAG = "verbose"


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
        click.echo(
            click.style(
                f"ERROR: Directory '{value}' does not exist.",
                fg="red",
                bold=True
            ),
            err=True
        )
        ctx.exit(1)

    if not value.is_dir():
        click.echo(
            click.style(
                f"ERROR: Path '{value}' is not a directory.",
                fg="red",
                bold=True
            ),
            err=True
        )
        ctx.exit(1)

    return value


def do_calculate_checksums(dir_path) -> bool:
    program = "C:\\Windows\\cfv.bat"
    result = subprocess.run([program, "-C", "-rr", "-t", "sha1"], cwd=dir_path)
    # print("returncode: " + str(result.returncode))
    # print(result)
    return result.returncode == 0


def do_verify_checksums(dir_path, checksum_file) -> bool:
    program = "C:\\Windows\\cfv.bat"
    result = subprocess.run([program, "-f", checksum_file], cwd=dir_path)
    # print("returncode: " + str(result.returncode))
    # print(result)
    return result.returncode == 0


@click.group()
@click.pass_context
@click.version_option("0.1.0", prog_name="checksum_file_tool")
@click.option("-v", "--verbose", is_flag=True, help="Display verbose output")
@click.argument(
    "dir_path",
    type=click.Path(resolve_path=True, path_type=Path),
    callback=validate_dir_path,
)
def cli(ctx, dir_path, verbose):
    ctx.ensure_object(dict)
    ctx.obj[DIR_PATH_ARG] = dir_path
    ctx.obj[VERBOSE_FLAG] = verbose


@cli.command("check-context-object")
@click.pass_context
def checkContext(ctx):
    pprint.pprint(type(ctx.obj))
    pprint.pprint(ctx.obj)


@cli.command("check-4-missing-cfv-files")
@click.pass_context
def checkForMissingCfvFiles(ctx):
    """Check for missing checksum files (cfv format) in the
       specified directory.

    Args:
        ctx (_type_): context object that contains context info & data
    """

    # retrieve the dir_path argument from the context object
    # this is the directoryu path within which to start checking for
    # missing CFV format files
    dirPath = ctx.obj[DIR_PATH_ARG]
    verbose = ctx.obj[VERBOSE_FLAG]

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
    """Generate (cfv format) checksum files for each sub-directory
       found within the specified directory.

    Args:
        ctx (_type_): context object that contains context info & data
    """
    dirPath = ctx.obj[DIR_PATH_ARG]
    verbose = ctx.obj[VERBOSE_FLAG]

    countCfvFilesGenerated = 0
    countDirsScanned = 0

    with os.scandir(dirPath) as entries:
        for entry in entries:
            if entry.is_dir():
                countDirsScanned += 1
                sha1_checksum_filepath = os.path.join(entry.path, entry.name) + SHA1_EXT
                if not os.path.exists(sha1_checksum_filepath):
                    click.echo(f"Generating cfv checksum file for {entry.path} ...")
                    do_calculate_checksums(entry.path)
                    countCfvFilesGenerated += 1

        if countCfvFilesGenerated > 0:
            click.echo(
                click.style(
                    f"Generated cfv checksums for {countCfvFilesGenerated} directories",
                    fg="green",
                )
            )
        else:
            click.echo(
                click.style(
                    "No cfv files generated; all sub-directories appear to be up-to-date",
                    fg="green",
                )
            )

    if verbose:
        click.echo(f"Total sub-directories scanned: {countDirsScanned}")
        click.echo(f"Generated cfv checksums for {countCfvFilesGenerated} directories")


@cli.command("verify-cfv-files")
@click.pass_context
def verifyCfvFiles(ctx):
    """Recursively scan the specified dir_path and verify the
       (cfv format) checksum files found in its sub-directories.

    Args:
        ctx (_type_): context object that contains context info & data
    """
    dirPath = ctx.obj[DIR_PATH_ARG]

    countDirsScanned = 0
    countCfvFilesVerified = 0

    with os.scandir(dirPath) as entries:
        for entry in entries:
            if entry.is_dir():
                countDirsScanned += 1
                sha1_checksum_filepath = os.path.join(entry.path, entry.name) + SHA1_EXT
                click.echo(f"Verifying CFV checksum file in {entry.path} ...")
                if do_verify_checksums(entry.path, sha1_checksum_filepath):
                    countCfvFilesVerified += 1

    if countDirsScanned == 0:
        click.echo(
            click.style("ERROR: No sub-directories found", fg="red", bold=True),
            err=True
        )
        sys.exit(1)

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


if __name__ == "__main__":
    cli()
