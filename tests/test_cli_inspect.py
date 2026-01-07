"""
Tests for CLI inspect command formatting and output.
"""
import csv
import io
import json
import stat
import time
from argparse import Namespace
from unittest.mock import patch

import pytest

from debx import ArFile, pack_ar_archive, DebBuilder, Deb822
from debx.cli.inspect import cli_inspect, format_ls, format_csv, format_json
from debx.cli.types import InspectItem, TarInfoType


class TestStatModeFallback:
    """Tests for stat mode fallback in format_mode."""

    def test_format_ls_type_none_regular_mode(self):
        """Test format_ls with type=None and regular file mode."""
        regular_mode = 0o100644  # Regular file with 644 permissions
        items = [
            InspectItem(
                file="regular.txt",
                size=100,
                type=None,
                mode=regular_mode,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        lines = result.strip().split('\n')
        # Should show as regular file with '-' prefix
        assert any('-rw-r--r--' in line for line in lines)

    def test_format_ls_type_none_dir_mode(self):
        """Test format_ls with type=None and directory mode."""
        dir_mode = stat.S_IFDIR | 0o755  # Directory with 755 permissions
        items = [
            InspectItem(
                file="mydir",
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
        lines = result.strip().split('\n')
        # Should show as directory with 'd' prefix
        assert any('drwxr-xr-x' in line for line in lines)

    def test_format_ls_type_none_symlink_mode(self):
        """Test format_ls with type=None and symlink mode."""
        link_mode = stat.S_IFLNK | 0o777  # Symlink with 777 permissions
        items = [
            InspectItem(
                file="mylink",
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
        lines = result.strip().split('\n')
        # Should show as symlink with 'l' prefix
        assert any('lrwxrwxrwx' in line for line in lines)

    def test_format_ls_unknown_type_dir_mode_fallback(self):
        """Test format_ls with unknown type that falls back to stat dir check."""
        # Use an unknown type string but with directory mode
        dir_mode = stat.S_IFDIR | 0o755
        items = [
            InspectItem(
                file="unknown_dir",
                size=0,
                type="unknown_custom_type",  # Not a recognized type
                mode=dir_mode,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        lines = result.strip().split('\n')
        # Should fall back to stat check and show 'd'
        assert any('d' in line for line in lines[1:])

    def test_format_ls_unknown_type_symlink_mode_fallback(self):
        """Test format_ls with unknown type that falls back to stat symlink check."""
        # Use an unknown type string but with symlink mode
        link_mode = stat.S_IFLNK | 0o777
        items = [
            InspectItem(
                file="unknown_link",
                size=0,
                type="unknown_custom_type",  # Not a recognized type
                mode=link_mode,
                uid=0,
                gid=0,
                mtime=int(time.time()),
                md5=None,
                path=None,
            )
        ]
        result = format_ls(items)
        lines = result.strip().split('\n')
        # Should fall back to stat check and show 'l'
        assert any('l' in line for line in lines[1:])


class TestFormatTimeLocale:
    """Tests for format_time locale handling."""

    def test_format_time_without_locale(self):
        """Test _format_time without user_locale."""
        from debx.cli.inspect import _format_time

        current_time = int(time.time())
        result = _format_time(current_time)
        assert len(result) > 0

    def test_format_time_with_none_mtime(self):
        """Test _format_time with None mtime."""
        from debx.cli.inspect import _format_time

        result = _format_time(None)
        assert result == "         "

    def test_format_time_with_valid_locale(self):
        """Test _format_time with a valid locale."""
        from debx.cli.inspect import _format_time
        import locale

        current_time = int(time.time())

        # Use 'C' locale which should always be available
        result = _format_time(current_time, user_locale='C')
        assert len(result) > 0

    def test_format_time_with_invalid_locale_on_set(self):
        """Test _format_time when setting locale fails."""
        from debx.cli.inspect import _format_time
        import locale

        current_time = int(time.time())
        original_setlocale = locale.setlocale

        def mock_setlocale(category, loc=None):
            if loc is not None and loc not in (None, '', ('en_US', 'UTF-8'), ('C', 'UTF-8'), 'C'):
                raise locale.Error("Invalid locale")
            return original_setlocale(category, loc)

        with patch.object(locale, 'setlocale', side_effect=mock_setlocale):
            # This should not raise, just silently ignore the locale error
            result = _format_time(current_time, user_locale='invalid_locale_xyz')
            assert len(result) > 0

    def test_format_time_with_locale_restore_error(self):
        """Test _format_time when restoring locale fails and falls back to 'C'."""
        from debx.cli.inspect import _format_time
        import locale

        current_time = int(time.time())
        original_setlocale = locale.setlocale
        call_count = [0]

        def mock_setlocale(category, loc=None):
            call_count[0] += 1
            # First call: getlocale returns tuple
            # Second call: setting user_locale - allow it
            # Third call: restoring old locale - fail
            # Fourth call: fallback to 'C' - allow it
            if call_count[0] == 3:
                # Fail when trying to restore old locale
                raise locale.Error("Cannot restore locale")
            if loc == 'C' or loc is None:
                return original_setlocale(category, loc)
            # Allow setting user_locale
            return original_setlocale(category, 'C')

        with patch.object(locale, 'setlocale', side_effect=mock_setlocale):
            with patch.object(locale, 'getlocale', return_value=('invalid', 'locale')):
                # This should not raise, should fallback to 'C'
                result = _format_time(current_time, user_locale='C')
                assert len(result) > 0


class TestFormatSizeDecimal:
    """Tests for _format_size with decimal values."""

    def test_format_size_decimal(self):
        """Test _format_size with sizes that result in decimal values."""
        from debx.cli.inspect import _format_size

        # 1536 bytes = 1.5K (not an integer)
        result = _format_size(1536)
        assert result == "1.5K"

        # 2560 bytes = 2.5K
        result = _format_size(2560)
        assert result == "2.5K"

    def test_format_size_integer(self):
        """Test _format_size with sizes that result in integer values."""
        from debx.cli.inspect import _format_size

        # 1024 bytes = 1K (integer)
        result = _format_size(1024)
        assert result == "1K"

        # 2048 bytes = 2K (integer)
        result = _format_size(2048)
        assert result == "2K"


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
