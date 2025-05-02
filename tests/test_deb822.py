import pytest

from debx.deb822 import Deb822


TEST_DEB822_CONTENT = """
Package: test-package
Version: 1.0
Description: Test package
 Long description
"""


@pytest.fixture
def sample_deb822():
    deb = Deb822()
    deb["Package"] = "test-pkg"
    deb["Version"] = "1.0"
    deb["Description"] = "Test package"
    return deb


def test_deb822_parse():
    deb = Deb822.parse(TEST_DEB822_CONTENT)

    assert deb["Package"] == "test-package"
    assert deb["Version"] == "1.0"
    assert deb["Description"].startswith("Test package\nLong description")
    assert len(deb) == 3


def test_deb822_dump():
    deb = Deb822()
    deb["Package"] = "test"
    deb["Version"] = "1.0"

    dumped = deb.dump()
    assert "Package: test" in dumped
    assert "Version: 1.0" in dumped


def test_deb822_from_file(tmp_path):
    test_file = tmp_path / "test.deb822"
    test_file.write_text(TEST_DEB822_CONTENT)

    deb = Deb822.from_file(test_file)
    assert deb["Package"] == "test-package"


def test_multiline_field():
    content = """Field: first line\n second line\n third line"""

    deb = Deb822.parse(content)
    assert deb["Field"] == "first line\nsecond line\nthird line"


def test_empty_field():
    deb = Deb822.parse("")
    assert len(deb) == 0


def test_comments_ignored():
    content = """# Comment\nPackage: test\n# Another comment"""

    deb = Deb822.parse(content)
    assert "Package" in deb
    assert "#" not in deb.keys()


def test_mapping_getitem(sample_deb822):
    assert sample_deb822["Package"] == "test-pkg"
    assert sample_deb822["Version"] == "1.0"
    with pytest.raises(KeyError):
        _ = sample_deb822["Nonexistent"]


def test_mapping_setitem(sample_deb822):
    sample_deb822["Architecture"] = "amd64"
    assert sample_deb822["Architecture"] == "amd64"
    sample_deb822["Version"] = "2.0"
    assert sample_deb822["Version"] == "2.0"


def test_mapping_delitem(sample_deb822):
    del sample_deb822["Description"]
    assert "Description" not in sample_deb822
    with pytest.raises(KeyError):
        del sample_deb822["Nonexistent"]


def test_mapping_len(sample_deb822):
    assert len(sample_deb822) == 3
    del sample_deb822["Version"]
    assert len(sample_deb822) == 2


def test_mapping_iter(sample_deb822):
    keys = set(sample_deb822)
    assert keys == {"Package", "Version", "Description"}


def test_mapping_contains(sample_deb822):
    assert "Package" in sample_deb822
    assert "Nonexistent" not in sample_deb822


def test_mapping_to_dict(sample_deb822):
    d = sample_deb822.to_dict()
    assert isinstance(d, dict)
    assert d["Package"] == "test-pkg"
    assert set(d.keys()) == {"Package", "Version", "Description"}


def test_mapping_clear():
    deb = Deb822({"a": 1, "b": 2})
    del deb["a"]
    del deb["b"]
    assert len(deb) == 0
    assert list(deb) == []


def test_mapping_update():
    deb = Deb822()
    deb.update({"Package": "pkg", "Version": "1.0"})
    assert deb["Package"] == "pkg"
    deb.update([("Arch", "amd64"), ("Priority", "optional")])
    assert set(deb.keys()) == {"Package", "Version", "Arch", "Priority"}
