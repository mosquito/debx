import logging
import sys
import tarfile
from argparse import Namespace
from pathlib import Path

from ..ar import unpack_ar_archive
from .types import TAR_EXTENSIONS


log = logging.getLogger(__name__)


def cli_unpack(args: Namespace) -> int:
    if args.directory is None:
        args.directory = args.package[:args.package.rfind(".deb")]

    unpack_to = Path(args.directory)
    unpack_to.mkdir(parents=True, exist_ok=True)

    files = []

    with open(args.package, "rb") as package_fp:
        for entry in unpack_ar_archive(package_fp):
            entry_path = unpack_to / entry.name
            log.info("Unpacking %s", entry_path)
            with entry_path.open("wb") as entry_fp:
                entry_fp.write(entry.content)

            files.append(entry_path)

    for file in files:
        if not any(file.name.endswith(ext) for ext in TAR_EXTENSIONS):
            continue

        target_dir = unpack_to / file.name[:file.name.find("tar") - 1]
        log.info("Unpacking %s -> %s", file.name, target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(file, "r:*") as tar:
            def extract_filter(tarinfo: tarfile.TarInfo, _: str) -> tarfile.TarInfo:
                log.info("Extracting %s/%s", target_dir, tarinfo.name)
                return tarinfo

            kw = {'filter': extract_filter} if sys.version_info >= (3, 12) else {}
            tar.extractall(path=target_dir, **kw)

        if not args.keep_archives:
            log.info("Removing packed %s", file.name)
            file.unlink()

    return 0
