import logging
from argparse import ArgumentParser
from pathlib import Path

from .cli.inspect import cli_inspect
from .cli.pack import cli_pack, parse_file
from .cli.types import Formatter
from .cli.unpack import cli_unpack
from .cli.sign import cli_sign


PARSER = ArgumentParser(formatter_class=Formatter)
PARSER.add_argument(
    "--log-level", help="Set the logging level", choices=["debug", "info", "warning", "error", "critical"],
    type=lambda x: getattr(logging, x.upper(), logging.INFO), default=logging.INFO,
)
SUBPARSERS = PARSER.add_subparsers()

PACK_DESCRIPTION = """
Pack a deb package manually. You can add control files and data files to the package.

Common format for files is:

 * source_path:destination_path[:modifiers]

Modifiers examples:

 * mode=0755 - set file permissions to 0755
 * uid=1000 - set file owner to 1000
 * gid=1000 - set file group to 1000
 * mtime=1234567890 - set file modification time to 1234567890
 
For example:

debx pack \\
    --control local_prerm:prerm \\
    --data local_file:/opt/test:mode=0755,uid=1000,gid=2000,mtime=1234567890
"""

PACK_PARSER = SUBPARSERS.add_parser(
    "pack", help="assemble any files or directories into a deb package",
    formatter_class=Formatter, description=PACK_DESCRIPTION,
)
PACK_PARSER.add_argument(
    "-c", "--control", nargs="*", type=parse_file, help="Control files to include in the package", default=(),
)
PACK_PARSER.add_argument(
    "-d", "--data", nargs="*", type=parse_file, help="Data files to include in the package", default=(),
)
PACK_PARSER.add_argument("-o", "--deb", help="Output deb file name", default="output.deb")
PACK_PARSER.set_defaults(func=cli_pack)


UNPACK_DESCRIPTION = """
Unpack a deb package. This will extract any debian package to a directory.

You can use this command to inspect the contents of a deb package.

For example:

debx unpack mypackage.deb -d /tmp/unpacked

This will unpack the package into /tmp/unpacked directory.

Usually you can see this directory in the deb package:

unpacked
├── control
│   ├── ...
│   └── md5sums
├── data
│   └── ...
└── debian-binary

It is a content of the common deb package.
"""

UNPACK_PARSER = SUBPARSERS.add_parser(
    "unpack", help="extract deb package content", description=UNPACK_DESCRIPTION, formatter_class=Formatter,
)
UNPACK_PARSER.add_argument("package", help="Deb package to unpack")
UNPACK_PARSER.add_argument(
    "-d", "--directory",
    help="Directory to unpack the package into, defaults to the package name without .deb extension",
)
UNPACK_PARSER.add_argument(
    "-k", "--keep-archives", action="store_true",
    help="Keep the original tar archives in the unpacked directory after extraction",
)
UNPACK_PARSER.set_defaults(func=cli_unpack)


INSPECT_DESCRIPTION = """
Inspect a deb package. This will print the contents of the deb package to the console.
You can use this command to inspect the contents of a deb package.
"""

INSPECT_PARSER = SUBPARSERS.add_parser(
    "inspect", help="Inspect a deb package", formatter_class=Formatter,
    description=INSPECT_DESCRIPTION,
)
INSPECT_FORMAT_HELP = """Output format:
 * json - structured obkect
 * csv - comma separated values
 * find - find-like output only file names
 * ls - ls -alh like output but contains files in archives
"""

INSPECT_PARSER.add_argument(
    "-f", "--format", choices=["json", "csv", "find", "ls"], default="ls", help=INSPECT_FORMAT_HELP,
)
INSPECT_PARSER.add_argument("package", help="Deb package to inspect")
INSPECT_PARSER.set_defaults(func=cli_inspect)

SIGN_DESCRIPTION = """
This subcommand signs a .deb package using GPG. The signing process has following steps:

1. Extract the payload from the .deb package
2. Sign the payload using GPG
3. Insert the signature into a new signed .deb package

Example:

debx sign --extract mypackage.deb | gpg --armor --detach-sign --output - | \
debx sign --update mypackage.deb -o mypackage.signed.deb

This extracts the payload, signs it via GPG, and embeds the signature as _gpgorigin into a new .deb package.
"""

SIGN_PARSER = SUBPARSERS.add_parser(
    "sign", help="Sign a deb package using GPG", formatter_class=Formatter,
    description=SIGN_DESCRIPTION,
)
SIGN_PARSER.add_argument(
    "-e", "--extract", action="store_true",
    help="Extract the payload from the deb package and write it to stdout",
)
SIGN_PARSER.add_argument(
    "-u", "--update", action="store_true",
    help="Update the deb package with the signature from stdin",
)
SIGN_PARSER.add_argument(
    "-o", "--output", type=Path, default=None,
    help="Output deb file name. By default same as package name but with signed suffix",
)
SIGN_PARSER.add_argument(
    "package", help="Deb package to extract or update", type=Path
)
SIGN_PARSER.set_defaults(func=cli_sign)


def main() -> None:
    args = PARSER.parse_args()
    logging.basicConfig(level=args.log_level, format="%(message)s")
    if hasattr(args, "func"):
        exit(args.func(args))
    else:
        PARSER.print_help()
        exit(1)


if __name__ == "__main__":
    main()
