# debx

A lightweight Python library for creating, reading, and manipulating Debian package (.deb) files.

## Features

- Read and extract content from Debian packages
- Create custom Debian packages programmatically
- Parse and manipulate Debian control files (RFC822-style format)
- Low-level AR archive manipulation
- No external dependencies - uses only Python standard library

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

## License

[MIT License](COPYING)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
