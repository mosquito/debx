import hashlib
import io
import logging
import tarfile
import time
from pathlib import Path, PurePosixPath
from tarfile import TarInfo
from typing import Iterable, NamedTuple, Optional, Union

from .ar import ArFile, pack_ar_archive


log = logging.getLogger(__name__)


class TarInfoContent(NamedTuple):
    tar_info: TarInfo
    content: bytes


class DebBuilder:
    def __init__(self):
        self.md5sums: dict[PurePosixPath, str] = {}
        self.data_files: dict[str, TarInfoContent] = dict()
        self.control_files: dict[str, TarInfoContent] = dict()
        self.directories = set()

    def add_control_entry(
        self,
        name: str,
        content: Union[str, bytes],
        mode: int = 0o644,
        mtime: int = -1,
    ) -> None:
        if isinstance(content, str):
            content = content.encode("utf-8")

        info = TarInfo(name)
        info.type = tarfile.REGTYPE
        info.size = len(content)
        info.mtime = mtime if mtime >= 0 else int(time.time())
        info.mode = mode
        self.control_files[info.name] = TarInfoContent(tar_info=info, content=content)

    def add_data_entry(
        self,
        content: bytes,
        name: Union[PurePosixPath, str],
        uid: int = 0,
        gid: int = 0,
        mode: int = 0o644,
        mtime: int = -1,
        symlink_to: Optional[Union[PurePosixPath, str]] = None,
    ) -> None:
        name = PurePosixPath(name)
        tar_info_path = name.relative_to("/")
        tar_info = tarfile.TarInfo(str(tar_info_path))

        if symlink_to:
            tar_info.type = tarfile.SYMTYPE
            tar_info.linkname = str(symlink_to)
            tar_info.size = 0
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

        self.data_files[tar_info.name] = TarInfoContent(tar_info=tar_info, content=content)

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
        for path, md5sum in self.md5sums.items():
            rel_path = path.relative_to("/") if path.is_absolute() else path
            md5sums.write(f"{md5sum}  {rel_path}\n".encode("utf-8"))

        md5sums_info = TarInfo("md5sums")
        md5sums_info.size = md5sums.tell()
        md5sums.seek(0)

        with io.BytesIO() as tarfp:
            with tarfile.open(fileobj=tarfp, mode="w:gz", format=tarfile.GNU_FORMAT, compresslevel=9) as tar:
                tar.addfile(md5sums_info, md5sums)
                for tarinfo, content in self.control_files.values():
                    log.debug("Adding control entry: %s", tarinfo.name)
                    tar.addfile(tarinfo, io.BytesIO(content))
            return tarfp.getvalue()

    def create_data_tar(self) -> bytes:
        with io.BytesIO() as fp:
            with tarfile.open(fileobj=fp, mode="w:bz2", format=tarfile.GNU_FORMAT, compresslevel=9) as tar:
                for directory_info in self.get_directories():
                    logging.debug(f"Adding directory to data archive: %s", directory_info.path)
                    tar.addfile(directory_info)

                for item in sorted(self.data_files.values(), key=lambda x: x.tar_info.name):
                    logging.debug(f"Adding data to archive: %s", item.tar_info.name)
                    if item.tar_info.type == tarfile.SYMTYPE:
                        tar.addfile(item.tar_info)
                    else:
                        tar.addfile(item.tar_info, io.BytesIO(item.content))

            return fp.getvalue()

    def pack(self) -> bytes:
        return pack_ar_archive(
            ArFile.from_bytes("2.0\n".encode("utf-8"), "debian-binary"),
            ArFile.from_bytes(self.create_control_tar(), "control.tar.gz"),
            ArFile.from_bytes(self.create_data_tar(), "data.tar.bz2"),
        )
