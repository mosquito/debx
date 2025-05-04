import tarfile
from argparse import ArgumentDefaultsHelpFormatter, RawTextHelpFormatter
from enum import Enum
from pathlib import PurePosixPath
from typing import Optional, TypedDict


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
    type: Optional[str]
    mode: Optional[int]
    uid: Optional[int]
    gid: Optional[int]
    mtime: Optional[int]
    md5: Optional[str]
    path: Optional[str]


TAR_EXTENSIONS = (".tar.xz", ".tar.gz", ".tar.bz2", ".tar")
