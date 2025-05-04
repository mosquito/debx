import io
import os
from argparse import ArgumentTypeError

import pytest
from unittest.mock import MagicMock, patch

from debx import ArFile, pack_ar_archive, unpack_ar_archive
from debx.cli.inspect import cli_inspect
from debx.cli.pack import parse_file, cli_pack
from debx.cli.sign import cli_sign_extract_payload, cli_sign_write_signature, cli_sign
from debx.cli.unpack import cli_unpack


class TestParseFile:
    def test_invalid_format(self):
        """Test that parse_file raises an error for invalid formats"""
        with pytest.raises(ArgumentTypeError, match="Invalid file format"):
            list(parse_file("no_colon_here"))

    def test_simple_file(self, tmp_path):
        """Test parsing a simple file with no modifiers"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = list(parse_file(f"{test_file}:/dest/path"))
        assert len(result) == 1
        assert str(result[0]["name"]) == "/dest/path"
        assert result[0]["content"] == b"test content"

    def test_file_with_modifiers(self, tmp_path):
        """Test parsing a file with modifiers"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = list(parse_file(f"{test_file}:/dest/path:mode=0755,uid=1000,gid=2000,mtime=1234567890"))
        assert len(result) == 1
        assert str(result[0]["name"]) == "/dest/path"
        assert result[0]["content"] == b"test content"
        assert result[0]["mode"] == 0o755
        assert result[0]["uid"] == 1000
        assert result[0]["gid"] == 2000
        assert result[0]["mtime"] == 1234567890

    def test_directory(self, tmp_path):
        """Test parsing a directory"""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        file1 = test_dir / "file1.txt"
        file1.write_text("file1 content")

        subdir = test_dir / "subdir"
        subdir.mkdir()

        file2 = subdir / "file2.txt"
        file2.write_text("file2 content")

        result = list(parse_file(f"{test_dir}:/dest/path"))
        assert len(result) == 2

        # Sort results to ensure consistent order for testing
        result.sort(key=lambda x: str(x["name"]))

        assert str(result[0]["name"]) == "/dest/path/file1.txt"
        assert result[0]["content"] == b"file1 content"

        assert str(result[1]["name"]) == "/dest/path/subdir/file2.txt"
        assert result[1]["content"] == b"file2 content"

    def test_relative_path_error(self, tmp_path):
        """Test that relative destination paths raise an error"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with pytest.raises(ArgumentTypeError, match="Destination path must be absolute"):
            list(parse_file(f"{test_file}:relative/path"))


@pytest.fixture
def test_package_structure(tmp_path):
    """Create a test package structure for integration tests"""
    # Create some control files
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    control_file = control_dir / "control"
    control_file.write_text(
        "Package: test-package\n"
        "Version: 1.0.0\n"
        "Architecture: all\n"
        "Maintainer: Test <test@example.com>\n"
        "Description: Test package\n"
        " This is a test package for testing purposes.\n"
    )

    # Create some data files
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    bin_dir = data_dir / "bin"
    bin_dir.mkdir(parents=True)

    bin_file = bin_dir / "test-script"
    bin_file.write_text("#!/bin/sh\necho 'Hello, world!'\n")
    bin_file.chmod(0o755)

    etc_dir = data_dir / "etc" / "test-package"
    etc_dir.mkdir(parents=True)

    config_file = etc_dir / "config"
    config_file.write_text("# Test configuration\nSETTING=value\n")

    return tmp_path


class TestIntegration:
    def test_pack_and_unpack(self, test_package_structure, tmp_path):
        """Integration test for packing and unpacking a deb package"""
        # Skip if running in CI without proper permissions
        if "CI" in os.environ:
            pytest.skip("Skipping integration test in CI environment")

        package_dir = test_package_structure
        output_deb = tmp_path / "output.deb"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Pack arguments
        pack_args = MagicMock()
        pack_args.control = [
            [{"content": (package_dir / "control" / "control").read_bytes(),
              "name": "control", "mode": 0o644}]
        ]
        pack_args.data = [
            [{"content": (package_dir / "data" / "bin" / "test-script").read_bytes(),
              "name": "/usr/bin/test-script", "mode": 0o755}],
            [{"content": (package_dir / "data" / "etc" / "test-package" / "config").read_bytes(),
              "name": "/etc/test-package/config", "mode": 0o644}]
        ]
        pack_args.deb = str(output_deb)

        # Run pack command
        cli_pack(pack_args)

        # Verify deb file was created
        assert output_deb.exists()

        # Unpack arguments
        unpack_args = MagicMock()
        unpack_args.package = str(output_deb)
        unpack_args.directory = str(extract_dir)

        # Run unpack command
        cli_unpack(unpack_args)

        # Verify files were extracted
        assert (extract_dir / "debian-binary").exists()
        assert (extract_dir / "control").exists()
        assert (extract_dir / "data").exists()


class TestInspect:
    def test_inspect(self, test_package_structure):
        """Test the inspect command"""
        package_dir = test_package_structure
        output_deb = package_dir / "output.deb"

        # Pack the package
        pack_args = MagicMock()
        pack_args.control = [
            [{"content": (package_dir / "control" / "control").read_bytes(),
              "name": "control", "mode": 0o644}]
        ]
        pack_args.data = [
            [{"content": (package_dir / "data" / "bin" / "test-script").read_bytes(),
              "name": "/usr/bin/test-script", "mode": 0o755}],
            [{"content": (package_dir / "data" / "etc" / "test-package" / "config").read_bytes(),
              "name": "/etc/test-package/config", "mode": 0o644}]
        ]
        pack_args.deb = str(output_deb)

        # Run pack command
        cli_pack(pack_args)

        # Inspect arguments
        inspect_args = MagicMock()
        inspect_args.package = str(output_deb)

        # Run inspect command
        cli_inspect(inspect_args)

        # Verify output
        assert output_deb.exists()

    def test_inspect_format_lst(self, test_package_structure):
        """Test the inspect command with --format=ls"""
        package_dir = test_package_structure
        output_deb = package_dir / "output.deb"

        # Pack the package
        pack_args = MagicMock()
        pack_args.control = [
            [{"content": (package_dir / "control" / "control").read_bytes(),
              "name": "control", "mode": 0o644}]
        ]
        pack_args.data = [
            [{"content": (package_dir / "data" / "bin" / "test-script").read_bytes(),
              "name": "/usr/bin/test-script", "mode": 0o755}],
            [{"content": (package_dir / "data" / "etc" / "test-package" / "config").read_bytes(),
              "name": "/etc/test-package/config", "mode": 0o644}]
        ]
        pack_args.deb = str(output_deb)

        # Run pack command
        cli_pack(pack_args)

        # Inspect arguments
        inspect_args = MagicMock()
        inspect_args.package = str(output_deb)
        inspect_args.format = 'ls'

        # Run inspect command
        cli_inspect(inspect_args)

        # Verify output
        assert output_deb.exists()

    def test_inspect_format_find(self, test_package_structure):
        """Test the inspect command with --format=find"""
        package_dir = test_package_structure
        output_deb = package_dir / "output.deb"

        # Pack the package
        pack_args = MagicMock()
        pack_args.control = [
            [{"content": (package_dir / "control" / "control").read_bytes(),
              "name": "control", "mode": 0o644}]
        ]
        pack_args.data = [
            [{"content": (package_dir / "data" / "bin" / "test-script").read_bytes(),
              "name": "/usr/bin/test-script", "mode": 0o755}],
            [{"content": (package_dir / "data" / "etc" / "test-package" / "config").read_bytes(),
              "name": "/etc/test-package/config", "mode": 0o644}]
        ]
        pack_args.deb = str(output_deb)

        # Run pack command
        cli_pack(pack_args)

        # Inspect arguments
        inspect_args = MagicMock()
        inspect_args.package = str(output_deb)
        inspect_args.format = 'find'

        # Run inspect command
        cli_inspect(inspect_args)

        # Verify output
        assert output_deb.exists()


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
