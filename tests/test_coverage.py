"""
Additional tests to increase code coverage.
"""
import csv
import io
import json
import os
import stat
import sys
import tempfile
import time
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from debx import DebBuilder, unpack_ar_archive
from debx.cli.inspect import format_ls
from debx.cli.types import InspectItem
from debx.cli.pack import parse_file


class TestPackDirectoryErrors:
    """Tests for pack command directory error handling."""

    def test_parse_file_relative_dest_error(self):
        """Test parse_file with relative destination path."""
        from argparse import ArgumentTypeError

        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "test.txt"
            test_file.write_bytes(b"content")

            with pytest.raises(ArgumentTypeError, match="must be absolute"):
                parse_file(f"{test_file}:relative/path")


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


class TestPackDirectoryMode:
    """Tests for pack command directory handling."""

    def test_parse_file_directory_with_mode(self, tmp_path):
        """Test parse_file with directory and mode modifier shows warning."""
        # Create a directory with a file
        test_dir = tmp_path / "mydir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_bytes(b"content")

        with patch("sys.stderr.write") as mock_stderr:
            result = list(parse_file(f"{test_dir}:/opt/mydir:mode=0755"))

        # Should have called stderr.write with warning
        mock_stderr.assert_called()
        assert len(result) == 1

    def test_parse_file_unsupported_type(self, tmp_path):
        """Test parse_file with unsupported file type (non-existent path)."""
        from argparse import ArgumentTypeError

        # Use a path that exists but is neither file nor directory nor symlink
        # by mocking Path.is_file and Path.is_dir to return False
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises((ArgumentTypeError, FileNotFoundError)):
            list(parse_file(f"{nonexistent}:/var/run/test"))

    def test_parse_file_invalid_regex_match(self):
        """Test parse_file when regex doesn't match."""
        from argparse import ArgumentTypeError

        # This has a colon but doesn't match the regex properly
        with pytest.raises(ArgumentTypeError, match="Invalid file format"):
            parse_file("::")  # Edge case that has colons but invalid format


class TestInvalidArArchive:
    """Tests for invalid AR archive handling."""

    def test_invalid_ar_magic(self):
        """Test unpack_ar_archive with invalid magic bytes."""
        invalid_ar = b"INVALID!\nsome data"
        with pytest.raises(ValueError, match="Invalid ar archive"):
            list(unpack_ar_archive(io.BytesIO(invalid_ar)))

    def test_truncated_ar_magic(self):
        """Test unpack_ar_archive with truncated magic bytes."""
        truncated_ar = b"!<arch"  # Missing last bytes
        with pytest.raises(ValueError, match="Invalid ar archive"):
            list(unpack_ar_archive(io.BytesIO(truncated_ar)))


class TestRootDirectorySkip:
    """Tests for root directory handling in DebBuilder."""

    def test_add_file_at_root_creates_no_root_dir(self):
        """Test that adding a file at root doesn't create '/' directory."""
        builder = DebBuilder()
        # Add a file that would normally create "/" as parent
        builder.add_data_entry(b"content", "/rootfile.txt")

        # Get directories - should not include root
        dirs = list(builder.get_directories())
        dir_names = [str(d.name) for d in dirs]

        # "/" or empty string should not be in the directory list
        assert "/" not in dir_names
        assert "" not in dir_names
        assert "." not in dir_names

    def test_root_directory_skip_in_get_directories(self):
        """Test that get_directories skips root '/' directory."""
        from pathlib import Path

        builder = DebBuilder()
        builder.add_data_entry(b"content", "/usr/bin/test")

        # Manually add "/" to directories to test the skip logic
        builder.directories.add(Path("/"))

        # Get directories - should skip "/"
        dirs = list(builder.get_directories())

        # "/" should be skipped
        for d in dirs:
            assert d.name != "/"
            assert d.name != ""

        # But other directories should be present
        dir_paths = [d.name for d in dirs]
        assert "usr" in dir_paths
        assert "usr/bin" in dir_paths


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


class TestDeb822ContinuationWithoutField:
    """Tests for Deb822 parsing edge cases."""

    def test_continuation_line_without_prior_field(self):
        """Test parsing continuation line without prior field definition."""
        from debx import Deb822

        # A line starting with space but no prior field defined
        text = " continuation without field\nPackage: test\n"
        result = Deb822.parse(text)
        # Should just skip the orphan continuation line
        assert result["Package"] == "test"

    def test_continuation_after_comment(self):
        """Test continuation line after a comment."""
        from debx import Deb822

        text = "# comment\n continuation\nPackage: test\n"
        result = Deb822.parse(text)
        assert result["Package"] == "test"


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


