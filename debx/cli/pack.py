import logging
import os
import re
import sys
from argparse import ArgumentTypeError, Namespace
from pathlib import Path, PurePosixPath
from typing import Iterable

from ..builder import DebBuilder
from .types import CLIFile


log = logging.getLogger(__name__)


def make_file(path: Path, dest: str, **kwargs) -> CLIFile:
    stat = path.stat()
    kwargs["content"] = path.read_bytes()

    dest_path = PurePosixPath(dest)

    if not dest_path.is_absolute():
        raise ArgumentTypeError(f"Destination path must be absolute: \"{dest_path!s}\"")

    kwargs["name"] = str(dest)

    if "uid" not in kwargs:
        kwargs["uid"] = 0
    if "gid" not in kwargs:
        kwargs["gid"] = 0
    if "mtime" not in kwargs:
        kwargs["mtime"] = int(stat.st_mtime)
    if "mode" not in kwargs:
        kwargs["mode"] = stat.st_mode & 0o777
    if path.is_symlink():
        kwargs["symlink_to"] = path.is_symlink()

    return CLIFile(**kwargs)

FILE_REGEXP = re.compile(r"^(?P<src>(?:[A-Za-z]:)?[^:]+):(?P<dest>(?:[A-Za-z]:)?[^:]+)(?::(?P<mods>.*))?$")

def parse_file(file: str) -> Iterable[CLIFile]:
    result = {}
    if ":" not in file:
        raise ArgumentTypeError(f"Invalid file format: {file!r} (should be src:dest[:modifiers])")

    match = FILE_REGEXP.match(file)
    if match is None:
        raise ArgumentTypeError(f"Invalid file format: {file!r}")

    groups = match.groupdict()

    src = groups["src"]
    dest = groups["dest"]
    modifiers = groups.get("mods", "") or ""

    for modifier in modifiers.split(","):
        if not modifier:
            continue
        key, value = modifier.split("=")
        result[key] = value

    if "uid" in result:
        result["uid"] = int(result["uid"])
    if "gid" in result:
        result["gid"] = int(result["gid"])
    if "mode" in result:
        result["mode"] = int(result["mode"], 8)
    if "mtime" in result:
        result["mtime"] = int(result["mtime"])

    path = Path(src)

    if path.is_dir():
        if "mode" in result:
            sys.stderr.write(
                f"{path} is a directory. Ignoring the mode for directories. Will be set from the original files\n",
            )
        dest_path = PurePosixPath(dest)
        files = []

        for subdir, dirs, subfiles in os.walk(path):
            subdir = Path(subdir)
            for fname in subfiles:
                subpath = Path(subdir) / fname

                stat = subpath.stat()
                files.append(
                    make_file(
                        subpath,
                        str(PurePosixPath("/", *dest_path.parts) / PurePosixPath(*subpath.relative_to(path).parts)),
                        uid=result.get("uid", stat.st_uid),
                        gid=result.get("gid", stat.st_gid),
                        mode=stat.st_mode & 0o777,
                        mtime=stat.st_mtime,
                    ),
                )
        return files
    elif path.is_file() or path.is_symlink():
        return [make_file(path, str(dest), **result)]

    raise ArgumentTypeError(f"File type is not supported: {file!r} (should be file symlink or directory)")


def cli_pack(args: Namespace) -> int:
    builder = DebBuilder()

    for files in args.control:
        for file in files:
            file.pop("symlink_to", None)
            log.info("Adding control file: %s", file["name"])
            file.pop("uid", None)
            file.pop("gid", None)
            file.pop("symlink_to", None)
            builder.add_control_entry(**file)

    for files in args.data:
        for file in files:
            log.info("Adding data file: %s", file["name"])
            builder.add_data_entry(**file)

    with open(args.deb, "wb") as f:
        f.write(builder.pack())
    return 0
