"""
Tests for CLI unpack command.
"""
import os
from argparse import Namespace

from debx import DebBuilder, Deb822
from debx.cli.unpack import cli_unpack


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

    def test_unpack_with_directory(self, tmp_path):
        """Test unpack with specified directory."""
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

        output_dir = tmp_path / "custom_output"
        args = Namespace(package=str(pkg_path), directory=str(output_dir), keep_archives=False)
        result = cli_unpack(args)

        assert result == 0
        assert output_dir.exists()
        assert (output_dir / "debian-binary").exists()
        assert (output_dir / "control").exists()
        assert (output_dir / "data").exists()
