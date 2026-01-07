"""
Tests for CLI entry point (__main__.py).
"""
import io
import sys
from unittest.mock import patch

import pytest

from debx import DebBuilder, Deb822


class TestEntryPoint:
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
