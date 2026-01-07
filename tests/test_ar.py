import io

import pytest
from io import BytesIO
from debx import ArFile, pack_ar_archive, unpack_ar_archive, EmptyHeaderError, TruncatedHeaderError, DebReader, \
    TruncatedDataError

TEST_CONTENT = b"test file content"
TEST_NAME = "testfile.txt"


@pytest.fixture
def sample_arfile() -> ArFile:
    return ArFile.from_bytes(data=TEST_CONTENT, name=TEST_NAME)


def test_arfile_dump(sample_arfile):
    dumped = sample_arfile.dump()
    assert dumped.startswith(TEST_NAME.encode('utf-8').ljust(16, b' '))
    assert TEST_CONTENT in dumped


def test_pack_unpack_roundtrip(sample_arfile):
    archive = pack_ar_archive(sample_arfile)

    unpacked_files = list(unpack_ar_archive(io.BytesIO(archive)))

    assert len(unpacked_files) == 1
    assert unpacked_files[0].name == TEST_NAME
    assert unpacked_files[0].content == TEST_CONTENT

    assert archive == pack_ar_archive(sample_arfile)


def test_empty_header_error():
    with pytest.raises(EmptyHeaderError):
        ArFile.parse_from_fp(BytesIO(b''))


def test_truncated_header_error():
    with pytest.raises(TruncatedHeaderError):
        ArFile.parse_from_fp(BytesIO(b'x' * 30))


def test_arfile_from_file(tmp_path):
    test_file = tmp_path / TEST_NAME
    test_file.write_bytes(TEST_CONTENT)
    ar_file = ArFile.from_file(test_file)

    assert ar_file.name == TEST_NAME
    assert ar_file.content == TEST_CONTENT


class TestReaderErrors:
    """Tests for DebReader error handling."""

    def test_missing_debian_binary(self):
        """Test error when debian-binary is missing."""
        # Create an AR archive without debian-binary
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"content", "control.tar.gz"),
            ArFile.from_bytes(b"content", "data.tar.bz2"),
        )
        with pytest.raises(KeyError, match="Missing 'debian-binary'"):
            DebReader(io.BytesIO(ar_content))

    def test_invalid_debian_binary_version(self):
        """Test error when debian-binary has wrong version."""
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"3.0\n", "debian-binary"),
            ArFile.from_bytes(b"content", "control.tar.gz"),
            ArFile.from_bytes(b"content", "data.tar.bz2"),
        )
        with pytest.raises(ValueError, match="Invalid debian-binary version"):
            DebReader(io.BytesIO(ar_content))

    def test_missing_data_tar(self):
        """Test error when data.tar is missing."""
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_bytes(b"content", "control.tar.gz"),
        )
        with pytest.raises(KeyError, match="Missing 'data.tar'"):
            DebReader(io.BytesIO(ar_content))

    def test_multiple_data_tar_files(self):
        """Test error when multiple data.tar files exist."""
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_bytes(b"content", "control.tar.gz"),
            ArFile.from_bytes(b"content", "data.tar.gz"),
            ArFile.from_bytes(b"content", "data.tar.bz2"),
        )
        with pytest.raises(ValueError, match="Multiple data.tar files"):
            DebReader(io.BytesIO(ar_content))

    def test_unsupported_compression(self):
        """Test error for unsupported compression format."""
        ar_content = pack_ar_archive(
            ArFile.from_bytes(b"2.0\n", "debian-binary"),
            ArFile.from_bytes(b"content", "control.tar.gz"),
            ArFile.from_bytes(b"content", "data.tar.xz"),
        )
        with pytest.raises(ValueError, match="Unsupported compression format"):
            DebReader(io.BytesIO(ar_content))


class TestArErrors:
    """Tests for AR archive error handling."""

    def test_truncated_data_error(self):
        """Test TruncatedDataError when data is incomplete."""
        # Create a header that claims more data than available
        header = b"testfile.txt    "  # 16 bytes name
        header += b"1234567890  "  # 12 bytes mtime
        header += b"0     "  # 6 bytes uid
        header += b"0     "  # 6 bytes gid
        header += b"100644  "  # 8 bytes mode
        header += b"1000      "  # 10 bytes size (claims 1000 bytes)
        header += b"\x60\x0A"  # 2 bytes magic

        ar_archive = b"!<arch>\n" + header + b"short"  # Only 5 bytes of data

        with pytest.raises(TruncatedDataError):
            list(unpack_ar_archive(io.BytesIO(ar_archive)))


class TestEmptyArArchive:
    """Tests for empty AR archive handling."""

    def test_empty_ar_archive(self):
        """Test unpacking empty AR archive."""
        # Just the AR magic, no files
        ar_content = b"!<arch>\n"
        files = list(unpack_ar_archive(io.BytesIO(ar_content)))
        assert files == []


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
