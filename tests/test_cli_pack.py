"""
Tests for CLI pack command.
"""
import tempfile
from argparse import ArgumentTypeError
from pathlib import Path
from unittest.mock import patch

import pytest

from debx.cli.pack import parse_file


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


class TestPackDirectoryErrors:
    """Tests for pack command directory error handling."""

    def test_parse_file_relative_dest_error(self):
        """Test parse_file with relative destination path."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "test.txt"
            test_file.write_bytes(b"content")

            with pytest.raises(ArgumentTypeError, match="must be absolute"):
                parse_file(f"{test_file}:relative/path")


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
        # Use a path that exists but is neither file nor directory nor symlink
        # by mocking Path.is_file and Path.is_dir to return False
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises((ArgumentTypeError, FileNotFoundError)):
            list(parse_file(f"{nonexistent}:/var/run/test"))

    def test_parse_file_invalid_regex_match(self):
        """Test parse_file when regex doesn't match."""
        # This has a colon but doesn't match the regex properly
        with pytest.raises(ArgumentTypeError, match="Invalid file format"):
            parse_file("::")  # Edge case that has colons but invalid format


class TestCliPack:
    """Tests for CLI pack command."""

    def test_parse_file_no_colon(self):
        """Test parse_file with missing colon."""
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
