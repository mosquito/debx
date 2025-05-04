import hashlib
import io
import tarfile

import pytest
from pathlib import PurePosixPath, Path

from debx import unpack_ar_archive, DebBuilder



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
