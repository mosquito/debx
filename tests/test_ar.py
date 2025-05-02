import io

import pytest
from io import BytesIO
from debx import ArFile, pack_ar_archive, unpack_ar_archive, EmptyHeaderError, TruncatedHeaderError


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
