import logging
import os
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
    kwargs["name"] = PurePosixPath(dest)

    if not kwargs["name"].is_absolute():
        raise ArgumentTypeError(f"Destination path must be absolute: \"{kwargs['name']!s}\"")

    if "uid" not in kwargs:
        kwargs["uid"] = stat.st_uid
    if "gid" not in kwargs:
        kwargs["gid"] = stat.st_gid
    if "mtime" not in kwargs:
        kwargs["mtime"] = int(stat.st_mtime)
    if "mode" not in kwargs:
        kwargs["mode"] = stat.st_mode & 0o777
    if path.is_symlink():
        kwargs["symlink_to"] = path.is_symlink()

    return CLIFile(**kwargs)


def parse_file(file: str) -> Iterable[CLIFile]:
    result = {}
    if ":" not in file:
        raise ArgumentTypeError(f"Invalid file format: {file!r} (should be src:dest[:modifiers])")
    src, dest = file.split(":", 1)
    if ":" in dest:
        dest, modifiers = dest.split(":", 1)
        for modifier in modifiers.split(","):
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
        dest_path = Path(dest)
        files = []

        for subdir, dirs, subfiles in os.walk(path):
            subdir = Path(subdir)
            for fname in subfiles:
                subpath = Path(subdir) / fname

                stat = subpath.stat()
                files.append(
                    make_file(
                        subpath,
                        str(dest_path / subpath.relative_to(path)),
                        uid=result.get("uid", stat.st_uid),
                        gid=result.get("gid", stat.st_gid),
                        mode=stat.st_mode & 0o777,
                        mtime=stat.st_mtime,
                    ),
                )
        return files
    elif path.is_file() or path.is_symlink():
        return [make_file(path, dest, **result)]

    raise ArgumentTypeError(f"File type is not supported: {file!r} (should be file symlink or directory)")


def cli_pack(args: Namespace) -> int:
    builder = DebBuilder()

    for files in args.control:
        for file in files:
            file.pop("symlink_to", None)
            log.info("Adding control file: %s", file["name"])
            builder.add_control_entry(**file)

    for files in args.data:
        for file in files:
            log.info("Adding data file: %s", file["name"])
            builder.add_data_entry(**file)

    with open(args.deb, "wb") as f:
        f.write(builder.pack())
    return 0
