import logging
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter, RawTextHelpFormatter, ArgumentTypeError
from pathlib import Path, PurePosixPath
from typing import TypedDict, Iterable

from .builder import DebBuilder
from .ar import unpack_ar_archive



log = logging.getLogger(__name__)


class Formatter(RawTextHelpFormatter, ArgumentDefaultsHelpFormatter):
    pass


class CLIFile(TypedDict, total=False):
    src: bytes
    dest: PurePosixPath
    mode: int
    uid: int
    gid: int
    mtime: int


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

    if 'uid' in result:
        result['uid'] = int(result['uid'])
    if 'gid' in result:
        result['gid'] = int(result['gid'])
    if 'mode' in result:
        result['mode'] = int(result['mode'], 8)
    if 'mtime' in result:
        result['mtime'] = int(result['mtime'])

    path = Path(src)

    if path.is_dir():
        if 'mode' in result:
            log.warning(
                f"%r is a directory. Ignoring the mode for directories. Will be set from the original files", path
            )
        dest_path = Path(dest)
        files = []

        for subdir, dirs, subfiles in path.walk():
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
                    )
                )
        return files
    elif path.is_file() or path.is_symlink():
        return [make_file(path, dest, **result)]

    raise ArgumentTypeError(f"File type is not supported: {file!r} (should be file symlink or directory)")

def cli_pack(args: Namespace) -> int:
    builder = DebBuilder()

    for files in args.control:
        for file in files:
            file.pop('symlink_to', None)
            log.info("Adding control file: %s", file["name"])
            builder.add_control_entry(**file)

    for files in args.data:
        for file in files:
            log.info("Adding data file: %s", file["name"])
            builder.add_data_entry(**file)

    with open(args.deb, "wb") as f:
        f.write(builder.pack())
    return 0


def cli_unpack(args: Namespace) -> int:
    unpack_to = Path(args.directory)
    unpack_to.mkdir(parents=True, exist_ok=True)
    with open(args.package, "rb") as package_fp:
        for entry in unpack_ar_archive(package_fp):
            log.info("Unpacking %s", entry.name)
            entry_path = unpack_to / entry.name
            with entry_path.open("wb") as entry_fp:
                entry_fp.write(entry.content)
    return 0


PARSER = ArgumentParser(formatter_class=Formatter)
PARSER.add_argument(
    "--log-level", help="Set the logging level", choices=["debug", "info", "warning", "error", "critical"],
    type=lambda x: getattr(logging, x.upper(), logging.INFO), default=logging.INFO
)
SUBPARSERS = PARSER.add_subparsers()

PACK_PARSER = SUBPARSERS.add_parser(
    'pack', formatter_class=Formatter,
    description='Pack a deb package manually. You can add control files and data files to the package.\n'
                'Common format for files is:\n\n'
                ' * source_path:destination_path[:modifiers]\n\n'
                'Modifiers examples:\n\n'
                ' * mode=0755 - set file permissions to 0755\n'
                ' * uid=1000 - set file owner to 1000\n'
                ' * gid=1000 - set file group to 1000\n'
                ' * mtime=1234567890 - set file modification time to 1234567890\n\n'
                'For example:\n'
                'debx pack \\\n'
                '\t--control local_prerm:prerm \\\n'
                '\t--data local_file:/opt/test:mode=0755,uid=1000,gid=2000,mtime=1234567890\n'
)
PACK_PARSER.add_argument(
    "-c", "--control", nargs="*", type=parse_file, help="Control files to include in the package", default=()
)
PACK_PARSER.add_argument(
    "-d", "--data", nargs="*", type=parse_file, help="Data files to include in the package", default=()
)
PACK_PARSER.add_argument("-o", "--deb", help="Output deb file name", default="output.deb")
PACK_PARSER.set_defaults(func=cli_pack)

UNPACK_PARSER = SUBPARSERS.add_parser(
    'unpack', description='Unpack a deb package', formatter_class=Formatter
)
UNPACK_PARSER.add_argument("package", help="Deb package to unpack")
UNPACK_PARSER.add_argument("-d", "--directory", help="Directory to unpack the package into", default=".")
UNPACK_PARSER.set_defaults(func=cli_unpack)


def main() -> None:
    args = PARSER.parse_args()
    logging.basicConfig(level=args.log_level, format="[%(levelname)s] %(message)s")
    if hasattr(args, 'func'):
        exit(args.func(args))
    else:
        PARSER.print_help()
        exit(1)


if __name__ == "__main__":
    main()
