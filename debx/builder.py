import hashlib
import io
import logging
import shutil
import tarfile
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from tarfile import TarInfo
from typing import IO, NamedTuple

from .ar import ArFile, pack_ar_archive


log = logging.getLogger(__name__)

DEFAULT_COMPRESSION_LEVEL = 9


class TarInfoContent(NamedTuple):
    tar_info: TarInfo
    content: bytes


class DataEntry(NamedTuple):
    tar_info: TarInfo
    content: bytes | Path


class DebBuilder:
    def __init__(self, compression_level: int = DEFAULT_COMPRESSION_LEVEL) -> None:
        self.compression_level = compression_level
        self.md5sums: dict[PurePosixPath, str] = {}
        self.data_files: dict[str, DataEntry] = {}
        self.control_files: dict[str, TarInfoContent] = {}
        self.directories: set[Path] = set()

    def add_control_entry(
        self,
        name: str,
        content: str | bytes,
        mode: int = 0o644,
        mtime: int = -1,
    ) -> None:
        if isinstance(content, str):
            content = content.encode("utf-8")

        file_path = PurePosixPath(name)
        if file_path.is_absolute():
            file_path = file_path.relative_to("/")

        info = TarInfo(str(file_path))
        info.type = tarfile.REGTYPE
        info.size = len(content)
        info.mtime = mtime if mtime >= 0 else int(time.time())
        info.mode = mode
        self.control_files[info.name] = TarInfoContent(tar_info=info, content=content)

    def add_data_entry(
        self,
        content: bytes | Path,
        name: PurePosixPath | str,
        uid: int = 0,
        gid: int = 0,
        mode: int = 0o644,
        mtime: int = -1,
        symlink_to: PurePosixPath | str | None = None,
    ) -> None:
        name = PurePosixPath(name)
        tar_info_path = name.relative_to("/")
        tar_info = tarfile.TarInfo(str(tar_info_path))

        if symlink_to:
            tar_info.type = tarfile.SYMTYPE
            tar_info.linkname = str(symlink_to)
            tar_info.size = 0
        elif isinstance(content, Path):
            md5 = hashlib.md5()
            with content.open("rb") as f:
                while chunk := f.read(1024 * 1024):
                    md5.update(chunk)
            self.md5sums[name] = md5.hexdigest()
            tar_info.type = tarfile.REGTYPE
            tar_info.size = content.stat().st_size
        else:
            self.md5sums[name] = hashlib.md5(content).hexdigest()
            tar_info = tarfile.TarInfo(str(tar_info_path))
            tar_info.type = tarfile.REGTYPE
            tar_info.size = len(content)

        tar_info.mtime = mtime if mtime >= 0 else int(time.time())
        tar_info.mode = mode
        tar_info.uid = uid
        tar_info.gid = gid

        current_path = Path("/")
        for part in name.parent.parts[1:]:
            current_path = current_path / part
            self.directories.add(current_path)

        self.data_files[tar_info.name] = DataEntry(tar_info=tar_info, content=content)

    def get_directories(self) -> Iterable[TarInfo]:
        now = time.time()
        for directory in sorted(self.directories):
            if directory == Path("/"):
                continue
            directory_archive_path = directory.relative_to("/")
            tar_info = TarInfo(str(directory_archive_path))
            tar_info.type = tarfile.DIRTYPE
            tar_info.mode = 0o755
            tar_info.mtime = int(now)
            yield tar_info

    def create_control_tar(self) -> bytes:
        md5sums = io.BytesIO()
        for path, md5sum in sorted(self.md5sums.items(), key=lambda x: x[0]):
            rel_path = path.relative_to("/") if path.is_absolute() else path
            md5sums.write(f"{md5sum}  {rel_path}\n".encode())

        md5sums_info = TarInfo("md5sums")
        md5sums_info.size = md5sums.tell()
        md5sums_info.mtime = int(time.time())
        md5sums.seek(0)

        with io.BytesIO() as tarfp:
            with tarfile.open(
                fileobj=tarfp,
                mode="w:gz",
                format=tarfile.GNU_FORMAT,
                compresslevel=self.compression_level,
            ) as tar:
                tar.addfile(md5sums_info, md5sums)
                for tarinfo, content in self.control_files.values():
                    log.debug("Adding control entry: %s", tarinfo.name)
                    tar.addfile(tarinfo, io.BytesIO(content))
            return tarfp.getvalue()

    def create_data_tar(self, fp: IO[bytes] | None = None) -> bytes:
        with io.BytesIO() as buf:
            with tarfile.open(
                fileobj=fp or buf,
                mode="w:bz2",
                format=tarfile.GNU_FORMAT,
                compresslevel=self.compression_level,
            ) as tar:
                for directory_info in self.get_directories():
                    logging.debug("Adding directory to data archive: %s", directory_info.path)
                    tar.addfile(directory_info)

                for item in sorted(self.data_files.values(), key=lambda x: x.tar_info.name):
                    logging.debug("Adding data to archive: %s", item.tar_info.name)
                    if item.tar_info.type == tarfile.SYMTYPE:
                        tar.addfile(item.tar_info)
                    elif isinstance(item.content, Path):
                        with item.content.open("rb") as f:
                            tar.addfile(item.tar_info, f)
                    else:
                        tar.addfile(item.tar_info, io.BytesIO(item.content))

            return buf.getvalue()

    def pack(self) -> bytes:
        return pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_bytes(self.create_control_tar(), "control.tar.gz"),
            ArFile.from_bytes(self.create_data_tar(), "data.tar.bz2"),
        )

    def write(self, fp: IO[bytes]) -> None:
        """Like pack(), but streams into fp: Path entries are never read into memory."""
        fp.write(
            pack_ar_archive(
                ArFile.from_bytes(b"2.0\n", "debian-binary"),
                ArFile.from_bytes(self.create_control_tar(), "control.tar.gz"),
            )
        )
        with tempfile.TemporaryFile() as data:
            self.create_data_tar(data)
            size = data.tell()
            data.seek(0)
            # writing header only. Contents will be streamed from the temporary file.
            fp.write(ArFile(name="data.tar.bz2", size=size, content=b"").header())
            shutil.copyfileobj(data, fp)
            if size % 2 != 0:
                fp.write(b"\n")
