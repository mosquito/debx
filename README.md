[![Coverage Status](https://coveralls.io/repos/github/mosquito/debx/badge.svg?branch=master)](https://coveralls.io/github/mosquito/debx?branch=master) [![tests](https://github.com/mosquito/debx/actions/workflows/tests.yml/badge.svg)](https://github.com/mosquito/debx/actions/workflows/tests.yml) ![PyPI - Version](https://img.shields.io/pypi/v/debx) ![PyPI - Types](https://img.shields.io/pypi/types/debx) ![PyPI - License](https://img.shields.io/pypi/l/debx)

# debx

![debx logo](https://raw.githubusercontent.com/mosquito/debx/master/logo.png "Logo")

Pronounced "deb-ex", `debx` is a Python library for creating, reading, and manipulating Debian package files.
This package includes the `debx` command-line tool for packing, unpacking, and inspecting any .deb packages.

## Features

- Cross-platform support for creating and unpacking .deb packages. Yes you can create .deb packages on Windows!
- Read and extract content from Debian packages
- Create custom Debian packages programmatically
- Parse and manipulate Debian control files (RFC822-style format)
- Low-level AR archive manipulation
- No external dependencies - uses only Python standard library
- Command-line interface for creating and unpacking .deb packages

## Installation

```bash
pip install debx
```

## Quick Start

### Reading a Debian Package

```python
from debx import DebReader

# Open a .deb file
with open("package.deb", "rb") as f:
    reader = DebReader(f)

    # Extract control file
    control_file = reader.control.extractfile("control")
    control_content = control_file.read().decode("utf-8")
    print(control_content)
    
    # List files in the data archive
    print(reader.data.getnames())
    
    # Extract a file from the data archive
    file_data = reader.data.extractfile("usr/bin/example").read()
```

### Creating a Debian Package

```python
from debx import DebBuilder, Deb822

# Initialize the builder
builder = DebBuilder()

# Create control information
control = Deb822({
    "Package": "example",
    "Version": "1.0.0",
    "Architecture": "all",
    "Maintainer": "Example Maintainer <maintainer@example.com>",
    "Description": "Example package\n This is an example package created with debx.",
    "Section": "utils",
    "Priority": "optional"
})

# Add control file
builder.add_control_entry("control", control.dump())

# Add files to the package
builder.add_data_entry(b"#!/bin/sh\necho 'Hello, world!'\n", "/usr/bin/example", mode=0o755)

# Add a symlink
builder.add_data_entry(b"", "/usr/bin/example-link", symlink_to="/usr/bin/example")

# Build the package
with open("example.deb", "wb") as f:
    f.write(builder.pack())
```

### Working with Debian Control Files

```python
from debx import Deb822

# Parse a control file
control = Deb822.parse("""
Package: example
Version: 1.0.0
Description: Example package
 This is a multi-line description
 with several paragraphs.
""")

print(control["Package"])  # "example"
print(control["Description"])  # Contains the full multi-line description

# Modify a field
control["Version"] = "1.0.1"

# Add a new field
control["Priority"] = "optional"

# Write back to string
print(control.dump())
```

## Command-Line Interface

debx includes a command-line interface for packing and unpacking Debian packages.

### Packing a Debian Package

The `pack` command allows you to create a .deb package from files on your system:

```bash
debx pack \
    --control control:/control \
              preinst:/preinst:mode=0755 \
    --data src/binary:/usr/bin/example:mode=0755 \
           src/config:/etc/example/config \
           src/directory:/opt/example \
    --output example.deb
```

The format for specifying files is:
```
source_path:absolute_destination_path[:modifier1,modifier2,...]
```

Modifiers is comma-separated list of options:
- `uid=1000` - Set file owner ID (by default is 0)
- `gid=1000` - Set file group ID (by default is 0)
- `mode=0755` - Set file permissions (by default is a source file mode will be kept)
- `mtime=1234567890` - Set file modification time (by default a source file mtime will be kept)

When specifying a directory, all files within that directory will be included in the package while preserving 
the directory structure.

Usually deb control files is:

* `control` - package metadata in Deb822 format. You can find more information about the control file format in the 
  [Debian Policy Manual](https://www.debian.org/doc/debian-policy/ch-controlfields.html)
* `preinst` - script to be executed before the package is installed
* `postinst` - script to be executed after the package is installed
* `prerm` - script to be executed before the package is removed
* `postrm` - script to be executed after the package is removed
* `md5sums` - list of files and their md5 checksums (generated automatically)
* `conffiles` - list of configuration files
* `triggers` - list of triggers
* `triggers-file` - list of files for triggers

A full list of control files can be found in the 
[Debian Policy Manual](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html).

### Unpacking a Debian Package

The `unpack` command extracts a .deb package into a directory:

```bash
debx unpack package.deb --directory output_dir
```

This will extract the internal AR archive members and tar archives 
(`debian-binary`, `control/`, `data/`) into the specified directory.

### Inspecting a Debian Package

The `inspect` command allows you to view the contents of a .deb package in different formats:

```bash
debx inspect package.deb  # --format=ls (default)
```

This will display the contents of the control file and the list of files in the data archive.

You can also specify the format to view the control file in different formats:

```bash
debx inspect --format=json package.deb 
```

See the `--help` option for more details on available formats.

### Package signing

The `sign` command allows you to sign a .deb package using GPG:

```bash
debx sign --extract mypackage.deb | \
  gpg --armor --detach-sign --output - | \
  debx sign --update mypackage.deb -o mypackage.signed.deb
```

This will extract the package, sign it with GPG, and update the package with the signature.
The `--extract` option extracts the package payload and streams it to stdout, which is then signed with GPG.
The `--update` option updates the package with the signature.

## License

[MIT License](COPYING)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.