import tarfile
from argparse import ArgumentDefaultsHelpFormatter, RawTextHelpFormatter
from enum import Enum
from pathlib import PurePosixPath
from typing import TypedDict


class Formatter(RawTextHelpFormatter, ArgumentDefaultsHelpFormatter):
    pass


class CLIFile(TypedDict, total=False):
    src: bytes
    dest: PurePosixPath
    mode: int
    uid: int
    gid: int
    mtime: int


class TarInfoType(bytes, Enum):
    regular = tarfile.REGTYPE
    hardlink = tarfile.LNKTYPE
    symlink = tarfile.SYMTYPE
    char = tarfile.CHRTYPE
    block = tarfile.BLKTYPE
    directory = tarfile.DIRTYPE
    fifo = tarfile.FIFOTYPE
    contiguous = tarfile.CONTTYPE


class InspectItem(TypedDict):
    file: str
    size: int
    type: str | None
    mode: int | None
    uid: int | None
    gid: int | None
    mtime: int | None
    md5: str | None
    path: str | None


TAR_EXTENSIONS = (".tar.xz", ".tar.gz", ".tar.bz2", ".tar")
