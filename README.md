[![Coverage Status](https://coveralls.io/repos/github/mosquito/debx/badge.svg?branch=master)](https://coveralls.io/github/mosquito/debx?branch=master) [![tests](https://github.com/mosquito/debx/actions/workflows/tests.yml/badge.svg)](https://github.com/mosquito/debx/actions/workflows/tests.yml) ![PyPI - Version](https://img.shields.io/pypi/v/debx) ![PyPI - Types](https://img.shields.io/pypi/types/debx) ![PyPI - License](https://img.shields.io/pypi/l/debx)

# debx

![debx logo](https://raw.githubusercontent.com/mosquito/debx/master/logo.png "Logo")

Pronounced "deb-ex", `debx` is a minimal Python library for creating, reading, and manipulating Debian package files (.deb). It includes a powerful command-line tool for packing, unpacking, inspecting, and signing packages.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [User Guide (CLI)](#user-guide-cli)
  - [Inspecting Packages](#inspecting-packages)
  - [Unpacking Packages](#unpacking-packages)
  - [Packing Packages](#packing-packages)
  - [Signing Packages](#signing-packages)
- [Developer Guide (Python API)](#developer-guide-python-api)
  - [Creating Packages with DebBuilder](#creating-packages-with-debbuilder)
  - [Reading Packages with DebReader](#reading-packages-with-debreader)
  - [Working with Control Files (Deb822)](#working-with-control-files-deb822)
  - [Low-Level AR Archive Operations](#low-level-ar-archive-operations)
- [Tutorials](#tutorials)
  - [Tutorial 1: Creating a Simple Package](#tutorial-1-creating-a-simple-package)
  - [Tutorial 2: Extracting and Modifying a Package](#tutorial-2-extracting-and-modifying-a-package)
  - [Tutorial 3: Building a Python Application Package](#tutorial-3-building-a-python-application-package)
- [API Reference](#api-reference)
- [License](#license)
- [Contributing](#contributing)

## Features

- **Cross-platform** - Create .deb packages on Linux, macOS, and Windows
- **Zero dependencies** - Uses only Python standard library
- **Full package lifecycle** - Read, create, modify, and sign packages
- **CLI and API** - Use from command line or integrate into Python applications
- **Type hints** - Full type annotation support for modern Python development
- **Multiple output formats** - Inspect packages as JSON, CSV, or ls-style output

## Installation

```bash
pip install debx
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install debx
```

Requires Python 3.10 or later.

## Quick Start

### 30-Second CLI Example

```bash
# Inspect a package
debx inspect mypackage.deb

# Unpack a package to a directory
debx unpack mypackage.deb -d ./unpacked

# Create a package from files
debx pack \
    --control control:/control \
    --data myapp:/usr/bin/myapp:mode=0755 \
    -o mypackage.deb
```

### 30-Second Python Example

<!-- name: test_quick_start -->
```python
import os
import tempfile
from debx import DebBuilder, Deb822

# Create a new package
builder = DebBuilder()

# Add control metadata
control = Deb822({
    "Package": "hello-world",
    "Version": "1.0.0",
    "Architecture": "all",
    "Maintainer": "You <you@example.com>",
    "Description": "A hello world package",
})
builder.add_control_entry("control", control.dump())

# Add an executable
builder.add_data_entry(
    b"#!/bin/sh\necho 'Hello, World!'\n",
    "/usr/bin/hello-world",
    mode=0o755
)

# Write the package
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "hello-world_1.0.0_all.deb")
    with open(path, "wb") as f:
        f.write(builder.pack())
    assert os.path.exists(path)
```

---

# User Guide (CLI)

The `debx` command-line tool provides four main commands for working with Debian packages.

## Inspecting Packages

The `inspect` command displays the contents of a .deb package.

### Basic Usage

```bash
debx inspect package.deb
```

This displays an `ls -lah` style listing of all files in the package:

```
total 42
-rw-r--r--  0 0     4 06 May 15:30 debian-binary
-rw-r--r--  0 0   512 06 May 15:30 control.tar.gz
-rw-r--r--  0 0   512 06 May 15:30 control.tar.gz/control
-rw-r--r--  0 0   128 06 May 15:30 control.tar.gz/md5sums
-rw-r--r--  0 0  1024 06 May 15:30 data.tar.bz2
drwxr-xr-x  0 0     0 06 May 15:30 data.tar.bz2/usr/
drwxr-xr-x  0 0     0 06 May 15:30 data.tar.bz2/usr/bin/
-rwxr-xr-x  0 0   256 06 May 15:30 data.tar.bz2/usr/bin/myapp
```

### Output Formats

Use the `--format` option to change the output format:

| Format | Description | Use Case |
|--------|-------------|----------|
| `ls` | ls -lah style (default) | Human-readable inspection |
| `json` | Structured JSON | Programmatic processing |
| `csv` | Comma-separated values | Spreadsheet import |
| `find` | File paths only | Piping to other tools |

#### JSON Format

```bash
debx inspect --format=json package.deb
```

```json
[
 {
  "file": "debian-binary",
  "size": 4,
  "type": "regular",
  "mode": 33188,
  "uid": 0,
  "gid": 0,
  "mtime": 1715006234,
  "md5": "a1b2c3d4e5f6...",
  "path": null
 }
]
```

#### CSV Format

```bash
debx inspect --format=csv package.deb > contents.csv
```

#### Find Format

```bash
debx inspect --format=find package.deb | grep usr/bin
```

### Logging

Enable debug logging to see detailed processing information:

```bash
debx --log-level=debug inspect package.deb
```

## Unpacking Packages

The `unpack` command extracts the contents of a .deb package.

### Basic Usage

```bash
debx unpack package.deb
```

This creates a directory named after the package (without `.deb` extension):

```
package/
├── control/
│   ├── control
│   ├── md5sums
│   ├── preinst
│   └── postinst
├── data/
│   └── usr/
│       └── bin/
│           └── myapp
└── debian-binary
```

### Specify Output Directory

```bash
debx unpack package.deb -d /tmp/extracted
```

### Keep Original Archives

By default, the tar archives are extracted and removed. To keep them:

```bash
debx unpack package.deb --keep-archives
```

This preserves `control.tar.gz` and `data.tar.bz2` alongside the extracted directories.

## Packing Packages

The `pack` command creates a .deb package from files and directories.

### Basic Usage

```bash
debx pack \
    --control path/to/control:/control \
    --data path/to/binary:/usr/bin/myapp:mode=0755 \
    -o mypackage.deb
```

### File Format Specification

Files are specified in the format:

```
source_path:destination_path[:modifiers]
```

| Component | Description |
|-----------|-------------|
| `source_path` | Local path to the file or directory |
| `destination_path` | Absolute path inside the package |
| `modifiers` | Optional comma-separated key=value pairs |

### Available Modifiers

| Modifier | Description | Example |
|----------|-------------|---------|
| `mode` | File permissions (octal) | `mode=0755` |
| `uid` | Owner user ID | `uid=1000` |
| `gid` | Owner group ID | `gid=1000` |
| `mtime` | Modification time (Unix timestamp) | `mtime=1715006234` |

### Control Files

Control files are added with the `-c` or `--control` option:

```bash
debx pack \
    --control control:/control \
    --control preinst:/preinst:mode=0755 \
    --control postinst:/postinst:mode=0755 \
    --control conffiles:/conffiles \
    --data ...
```

Common control files:

| File | Description |
|------|-------------|
| `control` | Package metadata (required) |
| `preinst` | Script run before installation |
| `postinst` | Script run after installation |
| `prerm` | Script run before removal |
| `postrm` | Script run after removal |
| `conffiles` | List of configuration files |
| `triggers` | Trigger definitions |
| `md5sums` | File checksums (auto-generated) |

For detailed control file specifications, see the [Debian Policy Manual](https://www.debian.org/doc/debian-policy/ch-controlfields.html).

### Adding Directories

Specify a directory as source to include all its contents recursively:

```bash
debx pack \
    --control control:/control \
    --data ./build/:/opt/myapp \
    -o mypackage.deb
```

The directory structure is preserved within the package.

### Complete Example

```bash
# Create control file
cat > control << 'EOF'
Package: myapp
Version: 1.0.0
Architecture: amd64
Maintainer: Developer <dev@example.com>
Description: My Application
 A longer description of my application
 spanning multiple lines.
Section: utils
Priority: optional
EOF

# Create postinst script
cat > postinst << 'EOF'
#!/bin/sh
echo "Installation complete!"
EOF

# Build the package
debx pack \
    --control control:/control \
    --control postinst:/postinst:mode=0755 \
    --data ./bin/myapp:/usr/bin/myapp:mode=0755 \
    --data ./lib/:/usr/lib/myapp \
    --data ./etc/config:/etc/myapp/config \
    -o myapp_1.0.0_amd64.deb
```

## Signing Packages

The `sign` command adds GPG signatures to .deb packages.

### How It Works

Signing is a two-step process:

1. **Extract** the payload from the package
2. **Sign** with GPG and **update** the package with the signature

### Complete Signing Workflow

```bash
debx sign --extract mypackage.deb | \
    gpg --armor --detach-sign --output - | \
    debx sign --update mypackage.deb -o mypackage.signed.deb
```

This pipeline:
1. Extracts the `control.tar` and `data.tar` from the package
2. Pipes them to GPG for signing
3. Embeds the signature as `_gpgorigin` in the new package

### Step-by-Step Signing

If you prefer separate steps:

```bash
# Extract payload to a file
debx sign --extract mypackage.deb > payload.bin

# Sign the payload
gpg --armor --detach-sign --output signature.asc payload.bin

# Update the package with signature
cat signature.asc | debx sign --update mypackage.deb -o mypackage.signed.deb
```

### Custom Output Path

By default, signed packages are named `<original>.signed.deb`. Specify a custom path:

```bash
debx sign --extract pkg.deb | gpg --armor --detach-sign | \
    debx sign --update pkg.deb -o /path/to/signed-pkg.deb
```

---

# Developer Guide (Python API)

## Creating Packages with DebBuilder

`DebBuilder` is the main class for programmatically creating .deb packages.

### Basic Usage

<!-- name: test_debbuilder_basic -->
```python
import os
import tempfile
from debx import DebBuilder, Deb822

builder = DebBuilder()

# Add control file (required)
control = Deb822({
    "Package": "mypackage",
    "Version": "1.0.0",
    "Architecture": "all",
    "Maintainer": "Developer <dev@example.com>",
    "Description": "Package description",
})
builder.add_control_entry("control", control.dump())

# Add data files
builder.add_data_entry(b"file content", "/path/in/package")

# Generate the package
deb_content = builder.pack()

# Write to file
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "mypackage.deb")
    with open(path, "wb") as f:
        f.write(deb_content)
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
```

### Adding Control Entries

<!-- name: test_add_control_entry -->
```python
from debx import DebBuilder

builder = DebBuilder()
builder.add_control_entry(
    name="control",           # Filename in control.tar.gz
    content="Package: test\nVersion: 1.0\nArchitecture: all\nMaintainer: Test <test@test.com>\nDescription: Test",
    mode=0o644,               # File permissions (default: 0o644)
    mtime=-1,                 # Modification time (-1 = current time)
)
assert "control" in builder.control_files
```

Common control entries:

<!-- name: test_common_control_entries -->
```python
from debx import DebBuilder, Deb822

builder = DebBuilder()
control = Deb822({
    "Package": "test",
    "Version": "1.0",
    "Architecture": "all",
    "Maintainer": "Test <test@test.com>",
    "Description": "Test package",
})

# Main control file
builder.add_control_entry("control", control.dump())

# Pre/post installation scripts
builder.add_control_entry("preinst", "#!/bin/sh\necho 'Pre-install'", mode=0o755)
builder.add_control_entry("postinst", "#!/bin/sh\necho 'Post-install'", mode=0o755)

# Pre/post removal scripts
builder.add_control_entry("prerm", "#!/bin/sh\necho 'Pre-remove'", mode=0o755)
builder.add_control_entry("postrm", "#!/bin/sh\necho 'Post-remove'", mode=0o755)

# Configuration files list
builder.add_control_entry("conffiles", "/etc/myapp/config\n")

assert len(builder.control_files) == 6
```

### Adding Data Entries

<!-- name: test_add_data_entry -->
```python
from debx import DebBuilder

builder = DebBuilder()
builder.add_data_entry(
    content=b"binary content",       # File content as bytes
    name="/usr/bin/myapp",           # Absolute path in package
    uid=0,                           # Owner user ID (default: 0)
    gid=0,                           # Owner group ID (default: 0)
    mode=0o755,                      # File permissions (default: 0o644)
    mtime=-1,                        # Modification time (-1 = current time)
    symlink_to=None,                 # Target path for symlinks
)
assert "usr/bin/myapp" in builder.data_files
```

### Creating Symlinks

<!-- name: test_create_symlinks -->
```python
from debx import DebBuilder

builder = DebBuilder()

# Create the target file
builder.add_data_entry(
    b"#!/bin/sh\necho 'Hello'\n",
    "/usr/bin/myapp",
    mode=0o755
)

# Create a symlink to it
builder.add_data_entry(
    b"",  # Empty content for symlinks
    "/usr/bin/myapp-link",
    symlink_to="/usr/bin/myapp"
)

assert "usr/bin/myapp" in builder.data_files
assert "usr/bin/myapp-link" in builder.data_files
```

### Reading Files from Disk

<!-- name: test_read_files_from_disk -->
```python
import os
import tempfile
from pathlib import Path
from debx import DebBuilder

builder = DebBuilder()

with tempfile.TemporaryDirectory() as tmp:
    # Create test files
    build_dir = Path(tmp) / "build"
    build_dir.mkdir()
    myapp = build_dir / "myapp"
    myapp.write_bytes(b"#!/bin/sh\necho hello")

    config_dir = Path(tmp) / "config"
    config_dir.mkdir()
    config_file = config_dir / "myapp.conf"
    config_file.write_bytes(b"key=value")

    # Read a file and add it to the package
    binary = myapp.read_bytes()
    builder.add_data_entry(binary, "/usr/bin/myapp", mode=0o755)

    # Add configuration file
    config = config_file.read_bytes()
    builder.add_data_entry(config, "/etc/myapp/myapp.conf", mode=0o644)

    assert "usr/bin/myapp" in builder.data_files
    assert "etc/myapp/myapp.conf" in builder.data_files
```

### Directory Handling

Directories are created automatically based on file paths:

<!-- name: test_directory_handling -->
```python
from debx import DebBuilder

builder = DebBuilder()

# This automatically creates /usr, /usr/share, and /usr/share/myapp directories
builder.add_data_entry(b"content", "/usr/share/myapp/data.txt")

assert len(builder.directories) == 3
```

### MD5 Checksums

MD5 checksums are automatically calculated and included in `control.tar.gz/md5sums`:

<!-- name: test_md5_checksums -->
```python
from pathlib import PurePosixPath
from debx import DebBuilder

builder = DebBuilder()
builder.add_data_entry(b"content", "/usr/bin/myapp")

# Access checksums before packing
assert PurePosixPath("/usr/bin/myapp") in builder.md5sums
assert builder.md5sums[PurePosixPath("/usr/bin/myapp")] == "9a0364b9e99bb480dd25e1f0284c8555"
```

## Reading Packages with DebReader

`DebReader` opens and reads existing .deb packages.

### Basic Usage

<!-- name: test_debreader_basic -->
```python
import io
from debx import DebBuilder, DebReader, Deb822

# First create a package to read
builder = DebBuilder()
control = Deb822({
    "Package": "test-pkg",
    "Version": "1.0.0",
    "Architecture": "all",
    "Maintainer": "Test <test@example.com>",
    "Description": "Test package",
})
builder.add_control_entry("control", control.dump())
builder.add_data_entry(b"test content", "/usr/bin/myapp")
builder.add_data_entry(b"config data", "/etc/myapp/config")
deb_content = builder.pack()

# Now read it
reader = DebReader(io.BytesIO(deb_content))

# Access control archive (tarfile.TarFile)
control_names = reader.control.getnames()
assert "control" in control_names
assert "md5sums" in control_names

# Access data archive (tarfile.TarFile)
data_names = reader.data.getnames()
assert "usr/bin/myapp" in data_names
assert "etc/myapp/config" in data_names
```

### Reading the Control File

<!-- name: test_read_control_file -->
```python
import io
from debx import DebBuilder, DebReader, Deb822

# Create a test package
builder = DebBuilder()
control = Deb822({
    "Package": "test-pkg",
    "Version": "2.0.0",
    "Architecture": "all",
    "Maintainer": "Test <test@example.com>",
    "Description": "A test package for reading",
})
builder.add_control_entry("control", control.dump())
builder.add_data_entry(b"data", "/usr/bin/test")
deb_content = builder.pack()

# Read and parse control file
reader = DebReader(io.BytesIO(deb_content))

control_member = reader.control.extractfile("control")
control_content = control_member.read().decode("utf-8")

parsed = Deb822.parse(control_content)

assert parsed["Package"] == "test-pkg"
assert parsed["Version"] == "2.0.0"
assert "test package" in parsed["Description"]
```

### Extracting Data Files

<!-- name: test_extract_data_files -->
```python
import io
import tempfile
from debx import DebBuilder, DebReader, Deb822

# Create a test package
builder = DebBuilder()
control = Deb822({
    "Package": "test-pkg",
    "Version": "1.0.0",
    "Architecture": "all",
    "Maintainer": "Test <test@example.com>",
    "Description": "Test",
})
builder.add_control_entry("control", control.dump())
builder.add_data_entry(b"binary content here", "/usr/bin/myapp")
deb_content = builder.pack()

reader = DebReader(io.BytesIO(deb_content))

# List all files
files = []
for member in reader.data.getmembers():
    files.append((member.name, member.size))
assert any("usr/bin/myapp" in f[0] for f in files)

# Extract a specific file
content = reader.data.extractfile("usr/bin/myapp").read()
assert content == b"binary content here"

# Extract to directory
with tempfile.TemporaryDirectory() as tmp:
    reader.data.extractall(tmp)
```

### Reading MD5 Checksums

<!-- name: test_read_md5sums -->
```python
import io
from debx import DebBuilder, DebReader, Deb822

# Create a test package
builder = DebBuilder()
control = Deb822({
    "Package": "test-pkg",
    "Version": "1.0.0",
    "Architecture": "all",
    "Maintainer": "Test <test@example.com>",
    "Description": "Test",
})
builder.add_control_entry("control", control.dump())
builder.add_data_entry(b"file content", "/usr/share/test/file.txt")
deb_content = builder.pack()

reader = DebReader(io.BytesIO(deb_content))

md5sums = reader.control.extractfile("md5sums")
checksums = {}
for line in md5sums.read().decode().splitlines():
    checksum, filepath = line.split(maxsplit=1)
    checksums[filepath.strip()] = checksum.strip()

assert "usr/share/test/file.txt" in checksums
```

## Working with Control Files (Deb822)

The `Deb822` class parses and generates Debian control file format (RFC 822 style).

### Parsing Control Files

<!-- name: test_deb822_parse -->
```python
from debx import Deb822

# Parse from string
control = Deb822.parse("""
Package: example
Version: 1.0.0
Architecture: all
Description: Short description
 This is a longer description that
 spans multiple lines.
""")

assert control["Package"] == "example"
assert control["Version"] == "1.0.0"
assert "Short description" in control["Description"]
assert "longer description" in control["Description"]
```

### Creating Control Files

<!-- name: test_deb822_create -->
```python
from debx import Deb822

# From dictionary
control = Deb822({
    "Package": "mypackage",
    "Version": "1.0.0",
    "Architecture": "amd64",
    "Maintainer": "Name <email@example.com>",
    "Depends": "libc6 (>= 2.17), libssl3",
    "Description": "Short description\n Long description line 1\n Long description line 2",
})

# Generate control file content
content = control.dump()
assert "Package: mypackage" in content
assert "Version: 1.0.0" in content
assert "Architecture: amd64" in content
```

### Modifying Control Files

<!-- name: test_deb822_modify -->
```python
from debx import Deb822

existing_content = """
Package: mypackage
Version: 1.0.0
Depends: python3
Suggests: vim
"""

control = Deb822.parse(existing_content)

# Modify fields
control["Version"] = "2.0.0"

# Add new fields
control["Recommends"] = "nginx"

# Remove fields
del control["Suggests"]

# Check field existence
assert "Depends" in control
assert control["Depends"] == "python3"

# Iterate over fields
keys = list(control)
assert "Package" in keys
assert "Version" in keys

# Convert to dict
data = control.to_dict()
assert data["Version"] == "2.0.0"
assert "Suggests" not in data
```

### Reading from File

<!-- name: test_deb822_from_file -->
```python
import tempfile
from pathlib import Path
from debx import Deb822

with tempfile.TemporaryDirectory() as tmp:
    control_path = Path(tmp) / "control"
    control_path.write_text("""Package: test
Version: 1.0
Architecture: all
Maintainer: Test <test@test.com>
Description: Test package
""")

    control = Deb822.from_file(control_path)
    assert control["Package"] == "test"
    assert control["Version"] == "1.0"
```

### Multi-line Fields

Multi-line values use continuation lines (starting with space):

<!-- name: test_deb822_multiline -->
```python
from debx import Deb822

control = Deb822({
    "Description": "Short description\n"
                   "This is line 2 of the long description\n"
                   "This is line 3 of the long description",
})

dumped = control.dump()
assert "Description: Short description" in dumped
assert " This is line 2" in dumped
assert " This is line 3" in dumped
```

## Low-Level AR Archive Operations

For advanced use cases, you can work directly with AR archives.

### Reading AR Archives

<!-- name: test_read_ar_archives -->
```python
import io
from debx import DebBuilder, Deb822, unpack_ar_archive

# Create a package to read
builder = DebBuilder()
control = Deb822({
    "Package": "test",
    "Version": "1.0",
    "Architecture": "all",
    "Maintainer": "Test <test@test.com>",
    "Description": "Test",
})
builder.add_control_entry("control", control.dump())
builder.add_data_entry(b"data", "/usr/bin/test")
deb_content = builder.pack()

# Read the AR archive
files = []
for ar_file in unpack_ar_archive(io.BytesIO(deb_content)):
    files.append({
        "name": ar_file.name,
        "size": ar_file.size,
        "mode": oct(ar_file.mode),
        "uid": ar_file.uid,
        "gid": ar_file.gid,
    })

assert any(f["name"] == "debian-binary" for f in files)
assert any(f["name"] == "control.tar.gz" for f in files)
assert any(f["name"] == "data.tar.bz2" for f in files)
```

### Creating AR Archives

<!-- name: test_create_ar_archives -->
```python
import io
import tempfile
from pathlib import Path
from debx import ArFile, pack_ar_archive, unpack_ar_archive

# Create from bytes
file1 = ArFile.from_bytes(b"content", "filename.txt")

with tempfile.TemporaryDirectory() as tmp:
    # Create a test file
    test_file = Path(tmp) / "test.txt"
    test_file.write_bytes(b"test file content")

    # Create from file on disk
    file2 = ArFile.from_file(test_file, arcname="renamed.txt")

    # Create from file object
    data_file = Path(tmp) / "data.bin"
    data_file.write_bytes(b"binary data")
    with open(data_file, "rb") as f:
        file3 = ArFile.from_fp(f, "data.bin")

    # Pack into AR archive
    archive_content = pack_ar_archive(file1, file2, file3)

    # Verify
    unpacked = list(unpack_ar_archive(io.BytesIO(archive_content)))
    assert len(unpacked) == 3
    assert unpacked[0].name == "filename.txt"
    assert unpacked[1].name == "renamed.txt"
    assert unpacked[2].name == "data.bin"
```

### ArFile Properties

<!-- name: test_arfile_properties -->
```python
from debx import ArFile

ar_file = ArFile.from_bytes(b"content", "test.txt")

assert ar_file.name == "test.txt"       # Filename (max 16 chars)
assert ar_file.size == 7                # Content size in bytes
assert ar_file.content == b"content"    # Raw bytes content
assert ar_file.uid == 0                 # Owner user ID
assert ar_file.gid == 0                 # Owner group ID
assert ar_file.mode == 0o100644         # File mode (permissions)
assert ar_file.mtime > 0                # Modification time (Unix timestamp)
assert ar_file.fp.read() == b"content"  # BytesIO file object for content
```

---

# Tutorials

## Tutorial 1: Creating a Simple Package

Create a minimal "Hello World" package from scratch.

<!-- name: test_tutorial_simple_package -->
```python
import os
import tempfile
from debx import DebBuilder, Deb822

# 1. Initialize builder
builder = DebBuilder()

# 2. Create control metadata
control = Deb822({
    "Package": "hello-debx",
    "Version": "1.0.0",
    "Architecture": "all",
    "Maintainer": "Tutorial <tutorial@example.com>",
    "Description": "Hello World from debx\n"
                   "A simple example package created with the debx library.",
    "Section": "misc",
    "Priority": "optional",
})
builder.add_control_entry("control", control.dump())

# 3. Add executable script
script = b"""#!/bin/sh
echo "Hello from debx!"
echo "This package was created with Python."
"""
builder.add_data_entry(script, "/usr/bin/hello-debx", mode=0o755)

# 4. Add documentation
readme = b"""Hello Debx Package
==================

This is a demonstration package created with the debx Python library.

Usage: hello-debx
"""
builder.add_data_entry(readme, "/usr/share/doc/hello-debx/README")

# 5. Build and save
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "hello-debx_1.0.0_all.deb")
    with open(path, "wb") as f:
        f.write(builder.pack())

    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
    print("Package created: hello-debx_1.0.0_all.deb")
```

Install and test:

```bash
sudo dpkg -i hello-debx_1.0.0_all.deb
hello-debx
# Output: Hello from debx!
```

## Tutorial 2: Extracting and Modifying a Package

Read an existing package, modify it, and create a new version.

<!-- name: test_tutorial_modify_package -->
```python
import io
import os
import tempfile
from debx import DebReader, DebBuilder, Deb822

# First, create an "original" package to modify
original_builder = DebBuilder()
original_control = Deb822({
    "Package": "test-package",
    "Version": "1.0.0",
    "Architecture": "all",
    "Maintainer": "Test <test@example.com>",
    "Description": "Original package",
})
original_builder.add_control_entry("control", original_control.dump())
original_builder.add_data_entry(b"original binary", "/usr/bin/testapp", mode=0o755)
original_builder.add_data_entry(b"config data", "/etc/testapp/config", mode=0o644)
original_deb = original_builder.pack()

# 1. Read the original package
reader = DebReader(io.BytesIO(original_deb))

# Parse control file
control_content = reader.control.extractfile("control").read().decode()
control = Deb822.parse(control_content)

# Store all data files
data_files = {}
for member in reader.data.getmembers():
    if member.isfile():
        content = reader.data.extractfile(member).read()
        data_files[member.name] = {
            "content": content,
            "mode": member.mode,
            "uid": member.uid,
            "gid": member.gid,
        }

# 2. Modify the package
control["Version"] = "1.0.1"  # Bump version
control["Description"] = control["Description"] + "\n Modified with debx."

# 3. Rebuild the package
builder = DebBuilder()

# Add modified control
builder.add_control_entry("control", control.dump())

# Re-add all data files
for path, info in data_files.items():
    builder.add_data_entry(
        info["content"],
        f"/{path}",  # Add leading slash
        mode=info["mode"],
        uid=info["uid"],
        gid=info["gid"],
    )

# 4. Save the modified package
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "modified.deb")
    with open(path, "wb") as f:
        f.write(builder.pack())

    assert os.path.exists(path)

    # Verify the modification
    with open(path, "rb") as f:
        verify_reader = DebReader(f)
        verify_control = Deb822.parse(
            verify_reader.control.extractfile("control").read().decode()
        )
        assert verify_control["Version"] == "1.0.1"
        assert "Modified with debx" in verify_control["Description"]

print(f"Modified package: {control['Package']}_{control['Version']}")
```

## Tutorial 3: Building a Python Application Package

Package a Python application with configuration and systemd service.

<!-- name: test_tutorial_python_app -->
```python
import os
import tempfile
from debx import DebBuilder, Deb822

def build_python_app_package(output_dir):
    builder = DebBuilder()

    # Control file
    control = Deb822({
        "Package": "myapp",
        "Version": "2.0.0",
        "Architecture": "all",
        "Maintainer": "DevTeam <dev@company.com>",
        "Depends": "python3 (>= 3.10)",
        "Description": "My Python Application\n"
                       "A production-ready Python application\n"
                       "with systemd service integration.",
        "Section": "python",
        "Priority": "optional",
        "Homepage": "https://github.com/company/myapp",
    })
    builder.add_control_entry("control", control.dump())

    # Post-installation script
    postinst = """#!/bin/sh
set -e
echo "MyApp installed successfully!"
"""
    builder.add_control_entry("postinst", postinst, mode=0o755)

    # Pre-removal script
    prerm = """#!/bin/sh
set -e
echo "Removing MyApp..."
"""
    builder.add_control_entry("prerm", prerm, mode=0o755)

    # Configuration files list
    builder.add_control_entry("conffiles", "/etc/myapp/config.yaml\n")

    # Main application script
    app_script = b"""#!/usr/bin/env python3
import logging
from pathlib import Path

CONFIG_PATH = Path("/etc/myapp/config.yaml")

def main():
    print("MyApp is running...")

if __name__ == "__main__":
    main()
"""
    builder.add_data_entry(app_script, "/opt/myapp/app.py", mode=0o755)

    # Wrapper script
    wrapper = b"""#!/bin/sh
exec /usr/bin/python3 /opt/myapp/app.py "$@"
"""
    builder.add_data_entry(wrapper, "/usr/bin/myapp", mode=0o755)

    # Default configuration
    config = b"""# MyApp Configuration
server:
  host: 0.0.0.0
  port: 8080

logging:
  level: INFO
"""
    builder.add_data_entry(config, "/etc/myapp/config.yaml", mode=0o644)

    # Systemd service file
    service = b"""[Unit]
Description=MyApp Python Application
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/myapp
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""
    builder.add_data_entry(service, "/lib/systemd/system/myapp.service", mode=0o644)

    # Build package
    package_name = f"{control['Package']}_{control['Version']}_all.deb"
    package_path = os.path.join(output_dir, package_name)
    with open(package_path, "wb") as f:
        f.write(builder.pack())

    print(f"Built: {package_name}")
    return package_path

# Test the function
with tempfile.TemporaryDirectory() as tmp:
    path = build_python_app_package(tmp)
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
```

---

# API Reference

## DebBuilder

| Method | Description |
|--------|-------------|
| `add_control_entry(name, content, mode=0o644, mtime=-1)` | Add a file to control.tar.gz |
| `add_data_entry(content, name, uid=0, gid=0, mode=0o644, mtime=-1, symlink_to=None)` | Add a file to data.tar.bz2 |
| `pack()` | Build and return the .deb package as bytes |
| `create_control_tar()` | Generate control.tar.gz content |
| `create_data_tar()` | Generate data.tar.bz2 content |

**Properties:**
- `md5sums: dict[PurePosixPath, str]` - MD5 checksums of data files
- `data_files: dict` - Data entries to be packed
- `control_files: dict` - Control entries to be packed
- `directories: set` - Directories that will be created

## DebReader

| Attribute | Type | Description |
|-----------|------|-------------|
| `control` | `tarfile.TarFile` | Control archive (control.tar.gz) |
| `data` | `tarfile.TarFile` | Data archive (data.tar.*) |

## Deb822

| Method | Description |
|--------|-------------|
| `parse(text)` | Parse Deb822 format string |
| `from_file(path)` | Parse from file path |
| `dump()` | Generate Deb822 format string |
| `to_dict()` | Convert to dictionary |

Implements `MutableMapping[str, Any]` - supports `[]`, `in`, `del`, `len()`, iteration.

## AR Archive Functions

| Function | Description |
|----------|-------------|
| `pack_ar_archive(*files)` | Create AR archive from ArFile objects |
| `unpack_ar_archive(fp)` | Iterate ArFile objects from archive |

## ArFile

| Method | Description |
|--------|-------------|
| `from_bytes(data, name, **kwargs)` | Create from bytes |
| `from_file(path, arcname="")` | Create from file path |
| `from_fp(fp, name, **kwargs)` | Create from file object |
| `dump()` | Serialize to AR format |

**Attributes:** `name`, `size`, `content`, `uid`, `gid`, `mode`, `mtime`, `fp`

## Exceptions

| Exception | Description |
|-----------|-------------|
| `ARFileError` | Base exception for AR operations |
| `EmptyHeaderError` | AR header is empty |
| `TruncatedHeaderError` | AR header is incomplete |
| `TruncatedDataError` | AR data is incomplete |

---

# License

[MIT License](COPYING)

# Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
