# BlazeLang packages

Create a package from a project directory containing `package.json` and its
declared `main.blz`:

```text
blz package main.blz
```

This writes `<package-name>.blzp` beside the project directory. A `.blzp` is a
versioned binary container with the `BLZP\0` magic header, compressed module
data, package metadata, a file table, per-module SHA-256 hashes, and a
container SHA-256 checksum. The installer rejects an unsupported version,
truncated file, altered payload, unsafe module path, or altered module data.

Install an archive committed anywhere in a GitHub repository with:

```text
blz install githubuser/repo
```

The installer finds the repository's `.blzp`, downloads it, validates it,
installs declared GitHub dependencies recursively, and stores verified module
files in `%LOCALAPPDATA%\BlazeLang\packages` (or `BLZ_PACKAGE_HOME` when set).
Import a package by its
`package.json` name; its `main` module is supplied to the existing import
loader and its internal relative imports work normally.
