import hashlib
import io
import tarfile

import pytest
from pathlib import PurePosixPath, Path

from debx import unpack_ar_archive, DebBuilder, Deb822, DebReader


@pytest.fixture
def builder():
    return DebBuilder()


def test_add_control_entry(builder):
    builder.add_control_entry("control", "Package: test\nVersion: 1.0")
    assert len(builder.control_files) == 1

    builder.add_data_entry(b"data", PurePosixPath("/usr/bin/test"))
    control_tar = builder.create_control_tar()

    with tarfile.open(fileobj=io.BytesIO(control_tar), mode="r:gz") as tar:
        names = {member.name for member in tar.getmembers()}
        assert names == {"control", "md5sums"}


def test_add_data_entry(builder):
    test_data = b"test content"
    builder.add_data_entry(
        test_data,
        PurePosixPath("/usr/share/test"),
        mode=0o755,
        uid=1000,
        gid=1000
    )

    assert len(builder.data_files) == 1
    assert len(builder.directories) == 2

    tar_info, _ = next(iter(builder.data_files.values()))
    assert tar_info.mode == 0o755
    assert tar_info.uid == 1000
    assert tar_info.gid == 1000


def test_symlink_handling(builder):
    builder.add_data_entry(
        b"",
        PurePosixPath("/usr/bin/link"),
        symlink_to="/usr/bin/target"
    )

    tar_info, _ = next(iter(builder.data_files.values()))
    assert tar_info.type == tarfile.SYMTYPE
    assert tar_info.linkname == "/usr/bin/target"


def test_directory_creation(builder):
    builder.add_data_entry(
        b"data",
        PurePosixPath("/var/lib/test/file")
    )

    assert len(builder.directories) == 3
    dirs = sorted(builder.directories)
    assert Path(str(dirs[0])) == Path("/var")
    assert Path(str(dirs[1])) == Path("/var/lib")


def test_pack_roundtrip(builder, tmp_path):
    builder.add_control_entry("control", "Package: test\nVersion: 1.0")
    builder.add_data_entry(b"bin_data", PurePosixPath("/usr/bin/prog"))
    builder.add_data_entry(b"lib_data", PurePosixPath("/usr/lib/lib.so"))

    ar_archive = builder.pack()

    ar_files = list(unpack_ar_archive(io.BytesIO(ar_archive)))
    assert len(ar_files) == 3
    names = {f.name for f in ar_files}
    assert names == {"debian-binary", "control.tar.gz", "data.tar.bz2"}


def test_md5sum_calculation(builder):
    test_data = b"test data" * 1000
    builder.add_data_entry(test_data, PurePosixPath("/test/file"))

    assert len(builder.md5sums) == 1
    md5 = builder.md5sums[PurePosixPath("/test/file")]
    assert md5 == hashlib.md5(test_data).hexdigest()


class TestBuilderEdgeCases:
    """Tests for DebBuilder edge cases."""

    def test_add_control_entry_absolute_path(self):
        """Test add_control_entry with absolute path."""
        builder = DebBuilder()
        builder.add_control_entry("/control", "Package: test")
        # The path should be normalized
        assert "control" in builder.control_files

    def test_symlink_in_data_tar(self):
        """Test that symlinks are properly included in data.tar."""
        builder = DebBuilder()
        builder.add_data_entry(b"content", "/usr/bin/target", mode=0o755)
        builder.add_data_entry(b"", "/usr/bin/link", symlink_to="/usr/bin/target")

        control = Deb822({
            "Package": "test",
            "Version": "1.0",
            "Architecture": "all",
            "Maintainer": "Test <test@test.com>",
            "Description": "Test",
        })
        builder.add_control_entry("control", control.dump())

        deb_content = builder.pack()

        # Verify package can be read
        reader = DebReader(io.BytesIO(deb_content))
        names = reader.data.getnames()
        assert "usr/bin/target" in names
        assert "usr/bin/link" in names

    def test_directory_at_root(self):
        """Test that root directory is skipped."""
        builder = DebBuilder()
        builder.add_data_entry(b"content", "/file.txt")

        # get_directories should not include root
        dirs = list(builder.get_directories())
        for d in dirs:
            assert d.name != "/"


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
        builder = DebBuilder()
        builder.add_data_entry(b"content", "/usr/bin/test")

        # Get one of the existing directories to determine the path type used
        existing_dir = next(iter(builder.directories))
        # Create root path using the same path type for sorting compatibility
        root_path = type(existing_dir)("/")
        builder.directories.add(root_path)

        # Get directories - should skip "/"
        dirs = list(builder.get_directories())

        # "/" should be skipped
        for d in dirs:
            assert d.name != "/"
            assert d.name != ""

        # But other directories should be present
        # Normalize backslashes to forward slashes for cross-platform compatibility
        dir_parts = [PurePosixPath(d.name.replace("\\", "/")).parts for d in dirs]
        assert ("usr",) in dir_parts
        assert ("usr", "bin") in dir_parts
