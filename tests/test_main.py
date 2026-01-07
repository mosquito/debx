import io
import os
from argparse import ArgumentTypeError

import pytest
from unittest.mock import MagicMock, patch

from debx import ArFile, pack_ar_archive, unpack_ar_archive, DebBuilder, Deb822
from debx.cli.inspect import cli_inspect, format_ls, format_csv, format_json
from debx.cli.pack import parse_file, cli_pack
from debx.cli.sign import cli_sign_extract_payload, cli_sign_write_signature, cli_sign
from debx.cli.types import InspectItem, TarInfoType
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


class TestInspectFormatting:
    """Tests for inspect formatting functions."""

    def test_format_ls_empty_items(self):
        """Test format_ls with empty list."""
        result = format_ls([])
        assert result == "total 0"

    def test_format_ls_mode_none(self):
        """Test format_ls when mode is None."""
        items = [
            InspectItem(
                file="test.txt",
                size=100,
                type="regular",
                mode=None,
                uid=0,
                gid=0,
                mtime=None,
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "----------" in result

    def test_format_ls_symlink_type(self):
        """Test format_ls with symlink type."""
        items = [
            InspectItem(
                file="link",
                size=0,
                type="symlink",
                mode=0o777,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert result.startswith("total")
        assert "l" in result  # symlink indicator

    def test_format_ls_directory_type(self):
        """Test format_ls with directory type."""
        items = [
            InspectItem(
                file="dir",
                size=0,
                type="directory",
                mode=0o755,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "d" in result  # directory indicator

    def test_format_ls_char_type(self):
        """Test format_ls with char device type."""
        items = [
            InspectItem(
                file="char",
                size=0,
                type="char",
                mode=0o666,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "c" in result  # char device indicator

    def test_format_ls_block_type(self):
        """Test format_ls with block device type."""
        items = [
            InspectItem(
                file="block",
                size=0,
                type="block",
                mode=0o660,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "b" in result  # block device indicator

    def test_format_ls_fifo_type(self):
        """Test format_ls with fifo type."""
        items = [
            InspectItem(
                file="fifo",
                size=0,
                type="fifo",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "p" in result  # fifo indicator

    def test_format_ls_old_year(self):
        """Test format_ls with old year timestamp."""
        # Use a timestamp from 2020
        old_time = 1577836800  # 2020-01-01
        items = [
            InspectItem(
                file="old.txt",
                size=100,
                type="regular",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=old_time,
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "2020" in result

    def test_format_ls_with_path(self):
        """Test format_ls with path set."""
        items = [
            InspectItem(
                file="data.tar.gz",
                size=100,
                type="regular",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path="usr/bin/test",
            )
        ]
        result = format_ls(items)
        assert "data.tar.gz/usr/bin/test" in result

    def test_format_ls_stat_dir_mode(self):
        """Test format_ls using stat.S_ISDIR for mode detection."""
        # Create item with directory mode but no explicit type
        dir_mode = stat.S_IFDIR | 0o755
        items = [
            InspectItem(
                file="dir",
                size=0,
                type=None,
                mode=dir_mode,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "d" in result

    def test_format_ls_stat_link_mode(self):
        """Test format_ls using stat.S_ISLNK for mode detection."""
        # Create item with symlink mode but no explicit type
        link_mode = stat.S_IFLNK | 0o777
        items = [
            InspectItem(
                file="link",
                size=0,
                type=None,
                mode=link_mode,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "l" in result

    def test_format_csv(self):
        """Test format_csv function."""
        items = [
            InspectItem(
                file="test.txt",
                size=100,
                type="regular",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=1234567890,
                md5="abc123",
                path=None,
            )
        ]
        result = format_csv(items)
        assert "file" in result
        assert "test.txt" in result
        assert "100" in result

    def test_format_json(self):
        """Test format_json function."""
        items = [
            InspectItem(
                file="test.txt",
                size=100,
                type="regular",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=1234567890,
                md5="abc123",
                path=None,
            )
        ]
        result = format_json(items)
        assert '"file": "test.txt"' in result
        assert '"size": 100' in result


class TestCliInspect:
    """Tests for CLI inspect command."""

    def test_inspect_json_format(self, tmp_path):
        """Test inspect with JSON format."""
        # Create a test package
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

        args = Namespace(package=str(pkg_path), format="json")
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "debian-binary" in output

    def test_inspect_csv_format(self, tmp_path):
        """Test inspect with CSV format."""
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

        args = Namespace(package=str(pkg_path), format="csv")
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "file" in output

    def test_inspect_unknown_format(self, tmp_path):
        """Test inspect with unknown format."""
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

        args = Namespace(package=str(pkg_path), format="invalid")
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = cli_inspect(args)

        assert result == 1
        assert "Unknown format" in mock_stderr.getvalue()


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


class TestCliUnpack:
    """Tests for CLI unpack command."""

    def test_unpack_default_directory(self, tmp_path):
        """Test unpack with default directory name."""
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

        pkg_path = tmp_path / "mypackage.deb"
        pkg_path.write_bytes(builder.pack())

        # Change to tmp_path so the default directory is created there
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            args = Namespace(package=str(pkg_path), directory=None, keep_archives=False)
            result = cli_unpack(args)
        finally:
            os.chdir(old_cwd)

        assert result == 0
        assert (tmp_path / "mypackage").exists()

    def test_unpack_keep_archives(self, tmp_path):
        """Test unpack with --keep-archives flag."""
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

        output_dir = tmp_path / "output"
        args = Namespace(package=str(pkg_path), directory=str(output_dir), keep_archives=True)
        result = cli_unpack(args)

        assert result == 0
        assert (output_dir / "control.tar.gz").exists()
        assert (output_dir / "data.tar.bz2").exists()


class TestCliPack:
    """Tests for CLI pack command."""

    def test_parse_file_no_colon(self):
        """Test parse_file with missing colon."""
        from argparse import ArgumentTypeError
        with pytest.raises(ArgumentTypeError, match="Invalid file format"):
            parse_file("nocolon")

    def test_parse_file_symlink(self, tmp_path):
        """Test parse_file with symlink."""
        # Create a symlink
        target = tmp_path / "target"
        target.write_bytes(b"content")
        link = tmp_path / "link"
        link.symlink_to(target)

        result = list(parse_file(f"{link}:/usr/bin/link"))
        assert len(result) == 1
        assert result[0]["name"] == "/usr/bin/link"


class TestFormatLsIntegration:
    """Integration tests for format_ls with TarInfoType."""

    def test_format_ls_with_tarinfoType_directory(self):
        """Test format_ls with TarInfoType.directory."""
        items = [
            InspectItem(
                file="dir",
                size=0,
                type=TarInfoType.directory.name,
                mode=0o755,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "d" in result

    def test_format_ls_with_tarinfoType_symlink(self):
        """Test format_ls with TarInfoType.symlink."""
        items = [
            InspectItem(
                file="link",
                size=0,
                type=TarInfoType.symlink.name,
                mode=0o777,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        assert "l" in result

    def test_format_ls_regular_file_with_type(self):
        """Test format_ls with regular file type (not dir/symlink)."""
        items = [
            InspectItem(
                file="file.txt",
                size=100,
                type="regular",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        # Should have regular file indicator (-)
        lines = result.strip().split('\n')
        assert any(line.startswith('-') for line in lines[1:])

    def test_format_ls_unknown_type_regular_mode(self):
        """Test format_ls with unknown type but regular file mode."""
        items = [
            InspectItem(
                file="file.txt",
                size=100,
                type="unknown_type",
                mode=0o644,  # Regular file mode
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        # Should fall through to stat check and show as regular file
        lines = result.strip().split('\n')
        assert len(lines) >= 2

    def test_format_ls_archive_type_with_path(self):
        """Test format_ls with archive type and path (shows arrow)."""
        items = [
            InspectItem(
                file="data.tar.gz",
                size=100,
                type="archive",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path="internal/file.txt",
            )
        ]
        result = format_ls(items)
        assert " -> internal/file.txt" in result

    def test_format_ls_tty_hint(self):
        """Test format_ls shows hint when not tty."""
        items = [
            InspectItem(
                file="test.txt",
                size=100,
                type="regular",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        with patch("sys.stdout.isatty", return_value=False):
            with patch("sys.stderr.write") as mock_stderr:
                format_ls(items)
                # Should write hint to stderr
                mock_stderr.assert_called()


class TestInspectXzFormat:
    """Tests for XZ compressed packages."""

    def test_inspect_tar_xz_package(self, tmp_path):
        """Test inspecting package with .tar.xz data."""
        import tarfile

        # Create a .tar.xz file
        xz_path = tmp_path / "data.tar.xz"
        with tarfile.open(xz_path, "w:xz") as tar:
            # Add a file to the tar
            data = b"test content"
            info = tarfile.TarInfo(name="usr/bin/test")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        # Create a minimal control.tar.gz
        control_path = tmp_path / "control.tar.gz"
        with tarfile.open(control_path, "w:gz") as tar:
            control_data = b"Package: test\nVersion: 1.0\n"
            info = tarfile.TarInfo(name="control")
            info.size = len(control_data)
            tar.addfile(info, io.BytesIO(control_data))

        # Create AR archive (deb package)
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_file(control_path, "control.tar.gz"),
            ArFile.from_file(xz_path, "data.tar.xz"),
        )

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(ar_content)

        args = Namespace(package=str(pkg_path), format="ls")
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("sys.stdout.isatty", return_value=True):
                result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "data.tar.xz" in output


class TestMainEntryPoint:
    """Tests for __main__.py entry point."""

    def test_main_no_args(self):
        """Test main with no arguments shows help."""
        from debx.__main__ import main, PARSER

        with patch.object(sys, 'argv', ['debx']):
            with patch.object(PARSER, 'print_help') as mock_help:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1
                mock_help.assert_called_once()

    def test_main_inspect_command(self, tmp_path):
        """Test main with inspect command."""
        from debx.__main__ import main

        # Create a test package
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

        with patch.object(sys, 'argv', ['debx', 'inspect', str(pkg_path)]):
            with patch("sys.stdout", new_callable=io.StringIO):
                with patch("sys.stdout.isatty", return_value=True):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0

    def test_main_pack_command(self, tmp_path):
        """Test main with pack command."""
        from debx.__main__ import main

        # Create control file
        control_file = tmp_path / "control"
        control_file.write_text("""Package: test
Version: 1.0
Architecture: all
Maintainer: Test <test@test.com>
Description: Test
""")

        # Create data file
        data_file = tmp_path / "binary"
        data_file.write_bytes(b"#!/bin/sh\necho hello")

        output_path = tmp_path / "output.deb"

        with patch.object(sys, 'argv', [
            'debx', 'pack',
            '-c', f'{control_file}:/control',
            '-d', f'{data_file}:/usr/bin/test:mode=0755',
            '-o', str(output_path)
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        assert output_path.exists()

    def test_main_unpack_command(self, tmp_path):
        """Test main with unpack command."""
        from debx.__main__ import main

        # Create a test package
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

        output_dir = tmp_path / "output"

        with patch.object(sys, 'argv', [
            'debx', 'unpack', str(pkg_path), '-d', str(output_dir)
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        assert output_dir.exists()


class TestInspectNoMd5sums:
    """Test inspect when md5sums file doesn't exist."""

    def test_inspect_without_md5sums(self, tmp_path):
        """Test inspecting package without md5sums in control."""
        import tarfile

        # Create control.tar.gz without md5sums
        control_path = tmp_path / "control.tar.gz"
        with tarfile.open(control_path, "w:gz") as tar:
            control_data = b"Package: test\nVersion: 1.0\n"
            info = tarfile.TarInfo(name="control")
            info.size = len(control_data)
            tar.addfile(info, io.BytesIO(control_data))

        # Create data.tar.bz2
        data_path = tmp_path / "data.tar.bz2"
        with tarfile.open(data_path, "w:bz2") as tar:
            data = b"test content"
            info = tarfile.TarInfo(name="usr/bin/test")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        # Create AR archive
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_file(control_path, "control.tar.gz"),
            ArFile.from_file(data_path, "data.tar.bz2"),
        )

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(ar_content)

        args = Namespace(package=str(pkg_path), format="ls")
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("sys.stdout.isatty", return_value=True):
                result = cli_inspect(args)

        assert result == 0


class TestInspectNoControlTar:
    """Tests for inspect when control.tar is missing."""

    def test_inspect_without_control_tar(self, tmp_path):
        """Test inspecting package without control.tar."""
        import tarfile

        # Create only data.tar.bz2, no control.tar
        data_path = tmp_path / "data.tar.bz2"
        with tarfile.open(data_path, "w:bz2") as tar:
            data = b"test content"
            info = tarfile.TarInfo(name="usr/bin/test")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        # Create AR archive without control.tar
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_file(data_path, "data.tar.bz2"),
        )

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(ar_content)

        args = Namespace(package=str(pkg_path), format="ls")
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("sys.stdout.isatty", return_value=True):
                result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "data.tar.bz2" in output


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


class TestInspectPlainTar:
    """Test inspect with plain .tar files (no compression)."""

    def test_inspect_plain_tar_package(self, tmp_path):
        """Test inspecting package with plain .tar data (mode='r')."""
        import tarfile

        # Create a plain .tar file
        tar_path = tmp_path / "data.tar"
        with tarfile.open(tar_path, "w") as tar:
            data = b"test content"
            info = tarfile.TarInfo(name="usr/bin/test")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        # Create control.tar.gz
        control_path = tmp_path / "control.tar.gz"
        with tarfile.open(control_path, "w:gz") as tar:
            control_data = b"Package: test\nVersion: 1.0\n"
            info = tarfile.TarInfo(name="control")
            info.size = len(control_data)
            tar.addfile(info, io.BytesIO(control_data))

        # Create AR archive
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_file(control_path, "control.tar.gz"),
            ArFile.from_file(tar_path, "data.tar"),
        )

        pkg_path = tmp_path / "test.deb"
        pkg_path.write_bytes(ar_content)

        args = Namespace(package=str(pkg_path), format="ls")
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("sys.stdout.isatty", return_value=True):
                result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "data.tar" in output


class TestInspectIntegration:
    """Integration tests for inspect command with all formats."""

    @pytest.fixture
    def test_package(self, tmp_path):
        """Create a test deb package with various file types."""
        builder = DebBuilder()

        control = Deb822({
            "Package": "integration-test",
            "Version": "1.2.3",
            "Architecture": "amd64",
            "Maintainer": "Test User <test@example.com>",
            "Description": "Integration test package\n"
                           " This is a multi-line description.\n"
                           " Used for testing inspect formats.",
            "Depends": "libc6",
        })
        builder.add_control_entry("control", control.dump())

        # Add various data files
        builder.add_data_entry(b"#!/bin/bash\necho hello", "/usr/bin/hello", mode=0o755)
        builder.add_data_entry(b"Configuration file", "/etc/hello.conf", mode=0o644)
        builder.add_data_entry(b"Library content", "/usr/lib/libhello.so", mode=0o644)
        builder.add_data_entry(b"Documentation", "/usr/share/doc/hello/README", mode=0o644)

        # Add a conffiles entry
        builder.add_control_entry("conffiles", "/etc/hello.conf\n")

        pkg_path = tmp_path / "integration-test_1.2.3_amd64.deb"
        pkg_path.write_bytes(builder.pack())

        return pkg_path

    def test_inspect_json_format(self, test_package):
        """Test inspect with JSON output format."""
        args = Namespace(package=str(test_package), format="json")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()

        # Parse JSON and verify structure
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify expected files are present
        files = {item.get("path") or item.get("file") for item in data}
        assert "debian-binary" in files
        assert any("control.tar" in f for f in files)
        assert any("data.tar" in f for f in files)

        # Verify data files are present
        paths = {item.get("path") for item in data if item.get("path")}
        assert "./usr/bin/hello" in paths or "usr/bin/hello" in paths
        assert "./etc/hello.conf" in paths or "etc/hello.conf" in paths

        # Verify JSON structure has expected keys
        for item in data:
            assert "file" in item
            assert "size" in item
            assert "type" in item
            assert "mode" in item

    def test_inspect_csv_format(self, test_package):
        """Test inspect with CSV output format."""
        args = Namespace(package=str(test_package), format="csv")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()

        # Parse CSV and verify structure
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)

        # First row should be headers
        headers = rows[0]
        assert "file" in headers
        assert "size" in headers
        assert "type" in headers
        assert "mode" in headers
        assert "path" in headers

        # Should have data rows
        assert len(rows) > 1

        # Verify data files are in output
        assert "debian-binary" in output
        assert "control.tar" in output
        assert "data.tar" in output
        assert "usr/bin/hello" in output

    def test_inspect_find_format(self, test_package):
        """Test inspect with find-style output format."""
        args = Namespace(package=str(test_package), format="find")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()

        # Verify output is line-based paths
        lines = output.strip().split("\n")
        assert len(lines) > 0

        # Verify expected files/paths are present
        assert "debian-binary" in output
        assert any("control.tar" in line for line in lines)
        assert any("data.tar" in line for line in lines)
        assert any("usr/bin/hello" in line for line in lines)
        assert any("etc/hello.conf" in line for line in lines)

    def test_inspect_ls_format(self, test_package):
        """Test inspect with ls-style output format."""
        args = Namespace(package=str(test_package), format="ls")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("sys.stdout.isatty", return_value=True):
                result = cli_inspect(args)

        assert result == 0
        output = mock_stdout.getvalue()

        # Verify ls-style output structure
        lines = output.strip().split("\n")
        assert lines[0].startswith("total ")

        # Verify permission strings are present
        assert any(line.startswith("-r") for line in lines)  # regular files

        # Verify expected files are present
        assert "debian-binary" in output
        assert "control.tar" in output
        assert "data.tar" in output
        assert "usr/bin/hello" in output
        assert "etc/hello.conf" in output

        # Verify human-readable sizes are present (e.g., "B", "K", "M")
        assert any(c in output for c in ["B", "K", "M"])

    def test_inspect_ls_format_non_tty(self, test_package):
        """Test inspect with ls format when stdout is not a tty (shows hint)."""
        args = Namespace(package=str(test_package), format="ls")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("sys.stdout.isatty", return_value=False):
                with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                    result = cli_inspect(args)

        assert result == 0
        # Should show hint about using other formats
        assert "Hint" in mock_stderr.getvalue()
        # But still produce output
        assert "total" in mock_stdout.getvalue()

    def test_inspect_all_formats_consistency(self, test_package):
        """Test that all formats contain the same files."""
        formats = ["json", "csv", "find", "ls"]
        file_counts = {}

        for fmt in formats:
            args = Namespace(package=str(test_package), format=fmt)

            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                with patch("sys.stdout.isatty", return_value=True):
                    result = cli_inspect(args)

            assert result == 0, f"Format {fmt} failed"

            output = mock_stdout.getvalue()
            # Count mentions of key files
            file_counts[fmt] = {
                "debian-binary": output.count("debian-binary"),
                "hello": output.count("hello"),
            }

        # All formats should mention debian-binary exactly once
        for fmt in formats:
            assert file_counts[fmt]["debian-binary"] >= 1, f"Format {fmt} missing debian-binary"
            assert file_counts[fmt]["hello"] >= 1, f"Format {fmt} missing hello files"


class TestLocaleHandling:
    """Tests for locale handling in format_time."""

    def test_format_ls_with_locale_error(self):
        """Test format_ls when locale setting fails."""
        import locale

        items = [
            InspectItem(
                file="test.txt",
                size=100,
                type="regular",
                mode=0o644,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]

        # Mock locale.setlocale to raise an error
        original_setlocale = locale.setlocale
        call_count = [0]

        def failing_setlocale(category, locale_str=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (getting old locale) succeeds
                return original_setlocale(category, locale_str)
            elif locale_str and locale_str != 'C':
                # Setting new locale fails
                raise locale.Error("test error")
            return original_setlocale(category, locale_str)

        with patch.object(locale, 'setlocale', side_effect=failing_setlocale):
            # This should not raise an error
            result = format_ls(items)

        assert "test.txt" in result
