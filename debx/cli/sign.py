import logging
import sys
from argparse import Namespace

from debx.ar import unpack_ar_archive, pack_ar_archive, ArFile


log = logging.getLogger(__name__)


def cli_sign_extract_payload(args: Namespace) -> int:
    if sys.stdout.isatty():
        log.error("Please redirect not to a terminal")
        return 1

    args.package = args.package.resolve()

    control_file = None
    data_file = None

    with args.package.resolve().open("rb") as fp:
        for file in unpack_ar_archive(fp):
            if file.name.startswith("control.tar"):
                control_file = file
                continue
            if file.name.startswith("data.tar"):
                data_file = file
                continue

    if not control_file:
        log.error("No control file found in the package")
        return 1

    if not data_file:
        log.error("No data file found in the package")
        return 1

    log.info("Streaming %s file to stdout", control_file.name)
    sys.stdout.buffer.write(control_file.content)
    log.info("Streaming %s file to stdout", data_file.name)
    sys.stdout.buffer.write(data_file.content)

    log.info(
        "Finished streaming files to stdout. %s bytes written",
        len(control_file.content) + len(data_file.content)
    )

    return 0


def cli_sign_write_signature(args: Namespace) -> int:
    signature = sys.stdin.buffer.read()

    if not signature.startswith(b"-----BEGIN PGP SIGNATURE-----"):
        log.error("Invalid signature format.\n\n%s", signature)
        return 1

    package_files = []

    with args.package.resolve().open("rb") as fp:
        for file in unpack_ar_archive(fp):
            package_files.append(file)

    package_files.append(ArFile(
        name="_gpgorigin",
        size=len(signature),
        content=signature,
    ))

    with args.output.open("wb") as fp:
        fp.write(pack_ar_archive(*package_files))

    return 0


def cli_sign(args: Namespace) -> int:
    if args.extract and args.update:
        log.error("Cannot use --extract and --update at the same time")
        return 1

    if args.extract:
        if args.output:
            log.error("Cannot use --output with --extract")
            return 1
        return cli_sign_extract_payload(args)
    elif args.update:
        if not args.output:
            args.output = args.package.parent / f"{args.package.stem}.signed.deb"
        return cli_sign_write_signature(args)
    else:
        log.error("No action specified")
        return 1
