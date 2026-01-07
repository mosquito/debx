"""
Tests for CLI sign command.
"""
import io
from argparse import Namespace
from unittest.mock import patch, MagicMock

import pytest

from debx import ArFile, pack_ar_archive, unpack_ar_archive, DebBuilder, Deb822
from debx.cli.sign import cli_sign_extract_payload, cli_sign_write_signature, cli_sign


@pytest.fixture
def mock_package(tmp_path):
    control_file = ArFile(name="control.tar.gz", content=b"control content", size=15)
    data_file = ArFile(name="data.tar.gz", content=b"data content", size=12)
    package_path = tmp_path / "test.deb"
    package_path.write_bytes(pack_ar_archive(control_file, data_file))
    return package_path


def test_cli_sign_extract_payload(mock_package, capsys):
    args = MagicMock()
    args.package = mock_package
    args.output = None

    with patch("sys.stdout", new_callable=io.BytesIO) as mock_stdout:
        mock_stdout.buffer = mock_stdout

        result = cli_sign_extract_payload(args)
        assert result == 0

        output = mock_stdout.getvalue()
        assert b"control content" in output
        assert b"data content" in output


def test_cli_sign_write_signature(mock_package, tmp_path):
    signature = b"-----BEGIN PGP SIGNATURE-----\nMockSignature\n-----END PGP SIGNATURE-----"
    output_path = tmp_path / "signed.deb"

    args = MagicMock()
    args.package = mock_package
    args.output = output_path

    with patch("sys.stdin", new=io.BytesIO(signature)) as mock_stdin:
        mock_stdin.buffer = mock_stdin
        result = cli_sign_write_signature(args)
        assert result == 0

    with output_path.open("rb") as f:
        files = list(unpack_ar_archive(f))
        assert any(file.name == "_gpgorigin" and file.content == signature for file in files)


def test_cli_sign_invalid_arguments(mock_package):
    args = MagicMock()
    args.extract = True
    args.update = True
    args.package = mock_package
    args.output = None

    with patch("debx.cli.sign.log.error") as mock_log:
        result = cli_sign(args)
        assert result == 1
        mock_log.assert_called_with("Cannot use --extract and --update at the same time")

    args.extract = False
    args.update = False

    with patch("debx.cli.sign.log.error") as mock_log:
        result = cli_sign(args)
        assert result == 1
        mock_log.assert_called_with("No action specified")


class TestCliSign:
    """Tests for CLI sign command."""

    def test_sign_extract_tty_error(self, tmp_path):
        """Test sign extract when stdout is tty."""
        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(b"dummy")

        args = Namespace(package=pkg_path, extract=True, update=False, output=None)

        with patch("sys.stdout.isatty", return_value=True):
            result = cli_sign_extract_payload(args)

        assert result == 1

    def test_sign_extract_no_control(self, tmp_path):
        """Test sign extract when control file is missing."""
        # Create package without control
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_bytes(b"data", "data.tar.bz2"),
        )
        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(ar_content)

        args = Namespace(package=pkg_path)

        with patch("sys.stdout.isatty", return_value=False):
            result = cli_sign_extract_payload(args)

        assert result == 1

    def test_sign_extract_no_data(self, tmp_path):
        """Test sign extract when data file is missing."""
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_bytes(b"control", "control.tar.gz"),
        )
        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(ar_content)

        args = Namespace(package=pkg_path)

        with patch("sys.stdout.isatty", return_value=False):
            result = cli_sign_extract_payload(args)

        assert result == 1

    def test_sign_write_invalid_signature(self, tmp_path):
        """Test sign write with invalid signature."""
        builder = DebBuilder()
        control = Deb822({
            "Package": "test",
            "Version": "1.0",
            "Architecture": "all",
            "Maintainer": "Test <test@test.com>",
            "Description": "Test",
        })
        builder.add_control_entry("control", control.dump())
        builder.add_data_entry(b"content", "/usr/bin/test")

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(builder.pack())

        output_path = tmp_path / "signed.deb"
        args = Namespace(package=pkg_path, output=output_path)

        with patch("sys.stdin.buffer.read", return_value=b"invalid signature"):
            result = cli_sign_write_signature(args)

        assert result == 1

    def test_sign_both_flags_error(self, tmp_path):
        """Test sign with both --extract and --update."""
        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(b"dummy")

        args = Namespace(package=pkg_path, extract=True, update=True, output=None)
        result = cli_sign(args)

        assert result == 1

    def test_sign_extract_with_output_error(self, tmp_path):
        """Test sign extract with --output flag."""
        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(b"dummy")

        args = Namespace(
            package=pkg_path, extract=True, update=False,
            output=tmp_path / "out.deb"
        )
        result = cli_sign(args)

        assert result == 1

    def test_sign_update_default_output(self, tmp_path):
        """Test sign update with default output path."""
        builder = DebBuilder()
        control = Deb822({
            "Package": "test",
            "Version": "1.0",
            "Architecture": "all",
            "Maintainer": "Test <test@test.com>",
            "Description": "Test",
        })
        builder.add_control_entry("control", control.dump())
        builder.add_data_entry(b"content", "/usr/bin/test")

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(builder.pack())

        signature = b"-----BEGIN PGP SIGNATURE-----\ntest\n-----END PGP SIGNATURE-----"

        args = Namespace(package=pkg_path, extract=False, update=True, output=None)

        with patch("sys.stdin.buffer.read", return_value=signature):
            result = cli_sign(args)

        assert result == 0
        assert (tmp_path / "test.signed.deb").exists()

    def test_sign_update_custom_output(self, tmp_path):
        """Test sign update with custom output path (covers branch 87->89)."""
        builder = DebBuilder()
        control = Deb822({
            "Package": "test",
            "Version": "1.0",
            "Architecture": "all",
            "Maintainer": "Test <test@test.com>",
            "Description": "Test",
        })
        builder.add_control_entry("control", control.dump())
        builder.add_data_entry(b"content", "/usr/bin/test")

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(builder.pack())

        signature = b"-----BEGIN PGP SIGNATURE-----\ntest\n-----END PGP SIGNATURE-----"

        custom_output = tmp_path / "custom_output.deb"
        args = Namespace(package=pkg_path, extract=False, update=True, output=custom_output)

        with patch("sys.stdin.buffer.read", return_value=signature):
            result = cli_sign(args)

        assert result == 0
        assert custom_output.exists()

    def test_sign_no_action_error(self, tmp_path):
        """Test sign with no action specified."""
        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(b"dummy")

        args = Namespace(package=pkg_path, extract=False, update=False, output=None)
        result = cli_sign(args)

        assert result == 1


class TestSignExtractSuccess:
    """Test successful sign extract operation."""

    def test_sign_extract_success(self, tmp_path):
        """Test sign extract with valid package."""
        builder = DebBuilder()
        control = Deb822({
            "Package": "test",
            "Version": "1.0",
            "Architecture": "all",
            "Maintainer": "Test <test@test.com>",
            "Description": "Test",
        })
        builder.add_control_entry("control", control.dump())
        builder.add_data_entry(b"content", "/usr/bin/test")

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(builder.pack())

        args = Namespace(package=pkg_path)

        # Create a mock stdout with buffer attribute
        mock_stdout = MagicMock()
        mock_stdout.isatty.return_value = False
        mock_stdout.buffer = io.BytesIO()

        with patch("sys.stdout", mock_stdout):
            result = cli_sign_extract_payload(args)

        assert result == 0
        assert len(mock_stdout.buffer.getvalue()) > 0

    def test_sign_extract_via_cli_sign(self, tmp_path):
        """Test sign extract success through cli_sign function (covers line 85)."""
        builder = DebBuilder()
        control = Deb822({
            "Package": "test",
            "Version": "1.0",
            "Architecture": "all",
            "Maintainer": "Test <test@test.com>",
            "Description": "Test",
        })
        builder.add_control_entry("control", control.dump())
        builder.add_data_entry(b"content", "/usr/bin/test")

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(builder.pack())

        args = Namespace(package=pkg_path, extract=True, update=False, output=None)

        # Create a mock stdout with buffer attribute
        mock_stdout = MagicMock()
        mock_stdout.isatty.return_value = False
        mock_stdout.buffer = io.BytesIO()

        with patch("sys.stdout", mock_stdout):
            result = cli_sign(args)

        assert result == 0
        assert len(mock_stdout.buffer.getvalue()) > 0
