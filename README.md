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

```python
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
with open("hello-world_1.0.0_all.deb", "wb") as f:
    f.write(builder.pack())
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

```python
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
with open("mypackage.deb", "wb") as f:
    f.write(deb_content)
```

### Adding Control Entries

```python
builder.add_control_entry(
    name="control",           # Filename in control.tar.gz
    content="Package: ...",   # String or bytes content
    mode=0o644,               # File permissions (default: 0o644)
    mtime=-1,                 # Modification time (-1 = current time)
)
```

Common control entries:

```python
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
```

### Adding Data Entries

```python
builder.add_data_entry(
    content=b"binary content",       # File content as bytes
    name="/usr/bin/myapp",           # Absolute path in package
    uid=0,                           # Owner user ID (default: 0)
    gid=0,                           # Owner group ID (default: 0)
    mode=0o755,                      # File permissions (default: 0o644)
    mtime=-1,                        # Modification time (-1 = current time)
    symlink_to=None,                 # Target path for symlinks
)
```

### Creating Symlinks

```python
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
```

### Reading Files from Disk

```python
from pathlib import Path

# Read a file and add it to the package
binary = Path("./build/myapp").read_bytes()
builder.add_data_entry(binary, "/usr/bin/myapp", mode=0o755)

# Add configuration file
config = Path("./config/myapp.conf").read_bytes()
builder.add_data_entry(config, "/etc/myapp/myapp.conf", mode=0o644)
```

### Directory Handling

Directories are created automatically based on file paths:

```python
# This automatically creates /usr, /usr/share, and /usr/share/myapp directories
builder.add_data_entry(b"content", "/usr/share/myapp/data.txt")
```

### MD5 Checksums

MD5 checksums are automatically calculated and included in `control.tar.gz/md5sums`:

```python
builder.add_data_entry(b"content", "/usr/bin/myapp")

# Access checksums before packing
print(builder.md5sums)
# {PurePosixPath('/usr/bin/myapp'): 'd41d8cd98f00b204e9800998ecf8427e'}
```

## Reading Packages with DebReader

`DebReader` opens and reads existing .deb packages.

### Basic Usage

```python
from debx import DebReader, Deb822

with open("package.deb", "rb") as f:
    reader = DebReader(f)

    # Access control archive (tarfile.TarFile)
    print(reader.control.getnames())
    # ['control', 'md5sums', 'postinst', ...]

    # Access data archive (tarfile.TarFile)
    print(reader.data.getnames())
    # ['usr/bin/myapp', 'etc/myapp/config', ...]
```

### Reading the Control File

```python
with open("package.deb", "rb") as f:
    reader = DebReader(f)

    # Extract and parse control file
    control_member = reader.control.extractfile("control")
    control_content = control_member.read().decode("utf-8")

    control = Deb822.parse(control_content)

    print(f"Package: {control['Package']}")
    print(f"Version: {control['Version']}")
    print(f"Description: {control['Description']}")
```

### Extracting Data Files

```python
with open("package.deb", "rb") as f:
    reader = DebReader(f)

    # List all files
    for member in reader.data.getmembers():
        print(f"{member.name} ({member.size} bytes)")

    # Extract a specific file
    content = reader.data.extractfile("usr/bin/myapp").read()

    # Extract to directory
    reader.data.extractall("/tmp/extracted")
```

### Reading MD5 Checksums

```python
with open("package.deb", "rb") as f:
    reader = DebReader(f)

    md5sums = reader.control.extractfile("md5sums")
    for line in md5sums.read().decode().splitlines():
        checksum, filepath = line.split(maxsplit=1)
        print(f"{filepath}: {checksum}")
```

## Working with Control Files (Deb822)

The `Deb822` class parses and generates Debian control file format (RFC 822 style).

### Parsing Control Files

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

print(control["Package"])      # "example"
print(control["Version"])      # "1.0.0"
print(control["Description"])  # "Short description\nThis is a longer..."
```

### Creating Control Files

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
print(content)
```

Output:
```
Package: mypackage
Version: 1.0.0
Architecture: amd64
Maintainer: Name <email@example.com>
Depends: libc6 (>= 2.17), libssl3
Description: Short description
 Long description line 1
 Long description line 2
```

### Modifying Control Files

```python
control = Deb822.parse(existing_content)

# Modify fields
control["Version"] = "2.0.0"

# Add new fields
control["Recommends"] = "nginx"

# Remove fields
del control["Suggests"]

# Check field existence
if "Depends" in control:
    print(control["Depends"])

# Iterate over fields
for key in control:
    print(f"{key}: {control[key]}")

# Convert to dict
data = control.to_dict()
```

### Reading from File

```python
from debx import Deb822

control = Deb822.from_file("/path/to/control")
```

### Multi-line Fields

Multi-line values use continuation lines (starting with space):

```python
control = Deb822({
    "Description": "Short description\n"
                   "This is line 2 of the long description\n"
                   "This is line 3 of the long description",
})

print(control.dump())
# Description: Short description
#  This is line 2 of the long description
#  This is line 3 of the long description
```

## Low-Level AR Archive Operations

For advanced use cases, you can work directly with AR archives.

### Reading AR Archives

```python
from debx import unpack_ar_archive

with open("package.deb", "rb") as f:
    for ar_file in unpack_ar_archive(f):
        print(f"Name: {ar_file.name}")
        print(f"Size: {ar_file.size}")
        print(f"Mode: {oct(ar_file.mode)}")
        print(f"UID/GID: {ar_file.uid}/{ar_file.gid}")
        print(f"MTime: {ar_file.mtime}")
        # Access content
        content = ar_file.content
```

### Creating AR Archives

```python
from debx import ArFile, pack_ar_archive

# Create from bytes
file1 = ArFile.from_bytes(b"content", "filename.txt")

# Create from file on disk
file2 = ArFile.from_file("/path/to/file", arcname="renamed.txt")

# Create from file object
with open("data.bin", "rb") as f:
    file3 = ArFile.from_fp(f, "data.bin")

# Pack into AR archive
archive_content = pack_ar_archive(file1, file2, file3)

with open("archive.ar", "wb") as f:
    f.write(archive_content)
```

### ArFile Properties

```python
ar_file = ArFile.from_bytes(b"content", "test.txt")

ar_file.name     # Filename (max 16 chars)
ar_file.size     # Content size in bytes
ar_file.content  # Raw bytes content
ar_file.uid      # Owner user ID
ar_file.gid      # Owner group ID
ar_file.mode     # File mode (permissions)
ar_file.mtime    # Modification time (Unix timestamp)
ar_file.fp       # BytesIO file object for content
```

---

# Tutorials

## Tutorial 1: Creating a Simple Package

Create a minimal "Hello World" package from scratch.

```python
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
with open("hello-debx_1.0.0_all.deb", "wb") as f:
    f.write(builder.pack())

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

```python
from debx import DebReader, DebBuilder, Deb822

# 1. Read the original package
with open("original.deb", "rb") as f:
    reader = DebReader(f)

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
with open("modified.deb", "wb") as f:
    f.write(builder.pack())

print(f"Modified package: {control['Package']}_{control['Version']}")
```

## Tutorial 3: Building a Python Application Package

Package a Python application with configuration and systemd service.

```python
from debx import DebBuilder, Deb822
from pathlib import Path
import stat

def build_python_app_package():
    builder = DebBuilder()

    # Control file
    control = Deb822({
        "Package": "myapp",
        "Version": "2.0.0",
        "Architecture": "all",
        "Maintainer": "DevTeam <dev@company.com>",
        "Depends": "python3 (>= 3.10), python3-pip",
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

# Create application user
if ! getent passwd myapp > /dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin myapp
fi

# Set ownership
chown -R myapp:myapp /opt/myapp
chown -R myapp:myapp /var/log/myapp

# Enable and start service
systemctl daemon-reload
systemctl enable myapp
systemctl start myapp

echo "MyApp installed successfully!"
"""
    builder.add_control_entry("postinst", postinst, mode=0o755)

    # Pre-removal script
    prerm = """#!/bin/sh
set -e

# Stop service before removal
if systemctl is-active --quiet myapp; then
    systemctl stop myapp
fi
systemctl disable myapp || true
"""
    builder.add_control_entry("prerm", prerm, mode=0o755)

    # Configuration files list
    builder.add_control_entry("conffiles", "/etc/myapp/config.yaml\n")

    # Application files
    # Main application script
    app_script = b"""#!/usr/bin/env python3
import yaml
import logging
from pathlib import Path

CONFIG_PATH = Path("/etc/myapp/config.yaml")
LOG_PATH = Path("/var/log/myapp/app.log")

def main():
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO)
    config = yaml.safe_load(CONFIG_PATH.read_text())
    logging.info(f"Starting MyApp with config: {config}")
    # Application logic here
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

features:
  debug_mode: false
"""
    builder.add_data_entry(config, "/etc/myapp/config.yaml", mode=0o644)

    # Systemd service file
    service = b"""[Unit]
Description=MyApp Python Application
After=network.target

[Service]
Type=simple
User=myapp
Group=myapp
ExecStart=/usr/bin/myapp
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    builder.add_data_entry(service, "/lib/systemd/system/myapp.service", mode=0o644)

    # Create log directory placeholder
    builder.add_data_entry(b"", "/var/log/myapp/.keep", mode=0o644)

    # Build package
    package_name = f"{control['Package']}_{control['Version']}_all.deb"
    with open(package_name, "wb") as f:
        f.write(builder.pack())

    print(f"Built: {package_name}")
    return package_name

if __name__ == "__main__":
    build_python_app_package()
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
