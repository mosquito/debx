import csv
import datetime
import hashlib
import io
import json
import locale
import logging
import math
import stat
import sys
import tarfile
from argparse import Namespace
from typing import Optional

from ..ar import unpack_ar_archive
from .types import TAR_EXTENSIONS, InspectItem, TarInfoType


log = logging.getLogger(__name__)


def format_ls(items: list[InspectItem]) -> str:
    if not sys.stdout.isatty():
        sys.stderr.write(
            "Hint: probably you trying process this output. Please see the output formats for better results.\n",
        )
    def format_size(size: int) -> str:
        if size == 0:
            return "0B"
        size_names = ("B", "K", "M", "G", "T", "P", "E", "Z", "Y")
        i = int(math.floor(math.log(size, 1024)))
        p = math.pow(1024, i)
        s = round(size / p, 1)
        if s.is_integer():
            s = int(s)
        return f"{s}{size_names[i]}"

    def format_mode(mode: Optional[int], item_type: Optional[str] = None) -> str:
        if mode is None:
            return "----------"

        result = ""

        if item_type is not None:
            if item_type == "directory" or (isinstance(item_type, TarInfoType) and item_type == TarInfoType.directory):
                result += "d"
            elif item_type == "symlink" or (isinstance(item_type, TarInfoType) and item_type == TarInfoType.symlink):
                result += "l"
            elif item_type == "char" or (isinstance(item_type, TarInfoType) and item_type == TarInfoType.char):
                result += "c"
            elif item_type == "block" or (isinstance(item_type, TarInfoType) and item_type == TarInfoType.block):
                result += "b"
            elif item_type == "fifo" or (isinstance(item_type, TarInfoType) and item_type == TarInfoType.fifo):
                result += "p"
            else:
                if stat.S_ISDIR(mode):
                    result += "d"
                elif stat.S_ISLNK(mode):
                    result += "l"
                else:
                    result += "-"
        else:
            if stat.S_ISDIR(mode):
                result += "d"
            elif stat.S_ISLNK(mode):
                result += "l"
            else:
                result += "-"
        result += "r" if mode & stat.S_IRUSR else "-"
        result += "w" if mode & stat.S_IWUSR else "-"
        result += "x" if mode & stat.S_IXUSR else "-"
        result += "r" if mode & stat.S_IRGRP else "-"
        result += "w" if mode & stat.S_IWGRP else "-"
        result += "x" if mode & stat.S_IXGRP else "-"
        result += "r" if mode & stat.S_IROTH else "-"
        result += "w" if mode & stat.S_IWOTH else "-"
        result += "x" if mode & stat.S_IXOTH else "-"
        return result

    def format_time(mtime: Optional[int], user_locale: Optional[str] = None) -> str:
        if mtime is None:
            return "         "

        old_locale = locale.getlocale(locale.LC_TIME)
        if user_locale:
            try:
                locale.setlocale(locale.LC_TIME, user_locale)
            except locale.Error:
                pass

        dt = datetime.datetime.fromtimestamp(mtime)
        now = datetime.datetime.now()

        if dt.year == now.year:
            result = dt.strftime("%d %b %H:%M")
        else:
            result = dt.strftime("%d %b  %Y")

        if user_locale:
            try:
                locale.setlocale(locale.LC_TIME, old_locale)
            except locale.Error:
                locale.setlocale(locale.LC_TIME, 'C')

        return result

    if not items:
        return "total 0"

    total_size = sum(item.get("size", 0) for item in items)
    total_blocks = (total_size + 1023) // 1024

    result = [f"total {total_blocks}"]

    max_uid_len = max(len(str(item.get("uid", 0))) for item in items)
    max_gid_len = max(len(str(item.get("gid", 0))) for item in items)

    for item in sorted(items, key=lambda x: x["file"]):
        if item.get("path"):
            file_name = item["file"] + "/" + item.get("path", "")
        else:
            file_name = item["file"]
        file_size = format_size(item.get("size", 0))
        file_mode = format_mode(item.get("mode", None), item.get("type", None))
        file_uid = str(item.get("uid", 0)).rjust(max_uid_len)
        file_gid = str(item.get("gid", 0)).rjust(max_gid_len)
        file_time = format_time(item.get("mtime", None))

        path_info = ""
        if item.get("path") and item.get("type") == "archive":
            path_info = f" -> {item['path']}"

        line = f"{file_mode}  {file_uid} {file_gid} {file_size.rjust(5)} {file_time} {file_name}{path_info}"
        result.append(line)

    return "\n".join(result) + "\n"


def format_find(items: list[InspectItem]) -> str:
    with io.StringIO() as stream:
        for row in items:
            if row["path"]:
                print(f"{row['file']}/{row['path']}", file=stream)
            else:
                print(row["file"], file=stream)
        return stream.getvalue()


def format_csv(items: list[InspectItem]) -> str:
    with io.StringIO() as f:
        writer = csv.writer(f)
        writer.writerow(items[0].keys())
        for row in items:
            writer.writerow(row.values())
        return f.getvalue()


def format_json(items: list[InspectItem]) -> str:
    with io.StringIO() as f:
        json.dump(items, f, indent=1)
        f.write("\n")
        return f.getvalue()


def cli_inspect(args: Namespace) -> int:
    data = []
    md5sums = {}
    control_tar = None
    control_tar_mode = None

    with open(args.package, "rb") as package_fp:
        for entry in unpack_ar_archive(package_fp):
            log.debug("Package entry: %s", entry.name)

            if not any(entry.name.endswith(ext) for ext in TAR_EXTENSIONS):
                data.append(
                    InspectItem(
                        file=entry.name,
                        size=entry.size,
                        type=TarInfoType.regular.name,
                        mode=entry.mode,
                        uid=entry.uid,
                        gid=entry.gid,
                        mtime=entry.mtime,
                        md5=hashlib.md5(entry.content).hexdigest(),
                        path=None,
                    ),
                )
                continue

            mode = "r"
            if entry.name.endswith(".tar.xz"):
                mode = "r:xz"
            elif entry.name.endswith(".tar.gz"):
                mode = "r:gz"
            elif entry.name.endswith(".tar.bz2"):
                mode = "r:bz2"

            if entry.name.startswith("control.tar"):
                control_tar = entry
                control_tar_mode = mode

            with tarfile.open(fileobj=entry.fp, mode=mode) as tar:
                data.append(
                    InspectItem(
                        file=entry.name,
                        size=entry.size,
                        type=TarInfoType.regular.name,
                        mode=entry.mode,
                        uid=entry.uid,
                        gid=entry.gid,
                        mtime=entry.mtime,
                        md5=hashlib.md5(entry.content).hexdigest(),
                        path=None,
                    ),
                )
                for tarinfo in tar:
                    log.debug("Tar entry: %s", tarinfo.name)
                    data.append(
                        dict(
                            file=entry.name,
                            size=tarinfo.size,
                            type=TarInfoType(tarinfo.type).name,
                            mode=tarinfo.mode,
                            uid=tarinfo.uid,
                            gid=tarinfo.gid,
                            mtime=tarinfo.mtime,
                            path=tarinfo.name,
                            md5=None,
                        ),
                    )

    if control_tar:
        with tarfile.open(fileobj=control_tar.fp, mode=control_tar_mode) as tar:
            for tarinfo in tar:
                log.debug("Control entry: %s", tarinfo.name)
                if tarinfo.name != "md5sums":
                    continue

                for md5line in tar.extractfile(tarinfo).read().decode().splitlines():
                    md5sum, path = md5line.split(maxsplit=1)
                    md5sums[path.strip()] = md5sum.strip()
                break

    for item in data:
        if not item['file'].startswith("data.tar"):
            continue

        item["md5"] = md5sums.get(item["path"], None)

    formatters = {
        "json": format_json,
        "csv": format_csv,
        "find": format_find,
        "ls": format_ls,
    }

    formatter = formatters.get(args.format)
    if formatter is None:
        sys.stderr.write(f"Unknown format: {args.format}\n")
        return 1

    sys.stdout.write(formatter(data))
    return 0
