import io

import pytest
from debx import DebBuilder, Deb822, DebReader


@pytest.fixture
def test_deb():
    builder = DebBuilder()

    control = Deb822({
        "Package": "test-package",
        "Version": "1.0.0",
        "Architecture": "all",
        "Maintainer": "Test User <test@example.com>",
        "Description": (
            "Test package for unit tests\n "
            "This is a test package created for unit testing the DebReader class."
        ),
        "Section": "test",
        "Priority": "optional"
    })

    builder.add_control_entry("control", control.dump())

    test_file_content = b"This is a test file content"
    builder.add_data_entry(test_file_content, "/usr/share/test-package/test.txt")

    return io.BytesIO(builder.pack())


def test_init(test_deb):
    reader = DebReader(test_deb)

    assert reader.control is not None
    assert reader.data is not None

    control_files = reader.control.getnames()
    assert "control" in control_files
    assert "md5sums" in control_files

    data_files = reader.data.getnames()
    assert "usr/share/test-package/test.txt" in data_files


def test_read_control_file(test_deb):
    """Test reading control file from the .deb package using Deb822"""
    reader = DebReader(test_deb)

    # Extract control file
    control_file = reader.control.extractfile("control")
    assert control_file is not None

    # Parse control file content using Deb822
    control_content = control_file.read().decode("utf-8")
    control = Deb822.parse(control_content)

    # Verify control file content
    assert control["Package"] == "test-package"
    assert control["Version"] == "1.0.0"
    assert control["Architecture"] == "all"
    assert "This is a test package created for unit testing" in control["Description"]


def test_read_data_file(test_deb):
    """Test reading data file from the .deb package"""
    reader = DebReader(test_deb)

    # Extract test file
    test_file = reader.data.extractfile("usr/share/test-package/test.txt")
    assert test_file is not None

    # Verify test file content
    content = test_file.read()
    assert content == b"This is a test file content"
