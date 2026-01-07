"""
Integration tests for CLI commands working together.
"""
import os
from unittest.mock import MagicMock

import pytest

from debx.cli.inspect import cli_inspect
from debx.cli.pack import cli_pack
from debx.cli.unpack import cli_unpack


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


class TestPackUnpackIntegration:
    """Integration tests for pack and unpack commands."""

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


class TestPackInspectIntegration:
    """Integration tests for pack and inspect commands."""

    def test_inspect(self, test_package_structure):
        """Test the inspect command on a packed package"""
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

    def test_inspect_format_ls(self, test_package_structure):
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
