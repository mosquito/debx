import io
import tarfile
from typing import IO, Literal

from .ar import unpack_ar_archive


class DebReader:
    control: tarfile.TarFile
    data: tarfile.TarFile

    def __init__(self, deb_fp: IO[bytes]):
        files = {}
        for file in unpack_ar_archive(deb_fp):
            files[file.name] = file

        if "debian-binary" not in files:
            raise KeyError("Missing 'debian-binary' in the archive")

        if files["debian-binary"].content != b"2.0\n":
            raise ValueError("Invalid debian-binary version")

        data_files = list(filter(lambda fp: fp.name.startswith("data.tar"), files.values()))
        if not data_files:
            raise KeyError("Missing 'data.tar' in the archive")

        if len(data_files) > 1:
            raise ValueError("Multiple data.tar files found in the archive")

        data_file_compression = data_files[0].name.split(".")[-1]
        data_mode: Literal["r:gz", "r:bz2"]
        if data_file_compression == "gz":
            data_mode = "r:gz"
        elif data_file_compression == "bz2":
            data_mode = "r:bz2"
        else:
            raise ValueError(f"Unsupported compression format: {data_file_compression}")

        # These TarFile handles are part of the public API and must outlive __init__.
        self.control = tarfile.open(fileobj=io.BytesIO(files["control.tar.gz"].content), mode="r:gz")  # noqa: SIM115
        self.data = tarfile.open(fileobj=io.BytesIO(data_files[0].content), mode=data_mode)  # noqa: SIM115
