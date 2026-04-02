---
title: Packaging
parent: Guides
nav_order: 6
description: Guide for packaging and publishing to PyPI
---

# Packaging Guide for PyPI

This guide outlines the steps to package the `open-bedrock-server` project and publish it to the Python Package Index (PyPI).

## Introduction

Publishing to PyPI makes your package easily installable for other Python users via `pip` (or `uv pip`). It also provides a central place for users to find your package and its documentation.

## Prerequisites

Before you begin, ensure you have:
1.  **Python installed**: Version 3.8 or higher (as specified in `pyproject.toml`).
2.  **`uv` installed**: A fast Python package installer. If not installed, see [uv installation guide](https://github.com/astral-sh/uv#installation).
3.  **Build tools**: `build` and `twine`. These will be installed in a later step.
4.  **PyPI Account**: Register an account on [PyPI](https://pypi.org/).
5.  **TestPyPI Account**: It's highly recommended to also register an account on [TestPyPI](https://test.pypi.org/) for testing your package before a live release.

## Packaging Steps

### Step 1: Update `pyproject.toml`

Your `pyproject.toml` file is the heart of your package's configuration. Ensure it's complete and accurate.

Key sections to review and update:

*   **Core Metadata**:
    *   `name`: Should be unique on PyPI. `open_bedrock_server` is likely fine.
    *   `version`: Update this for each new release (e.g., `0.1.0`, `0.1.1`, `0.2.0`).
    *   `authors`: Provide your name and email.
    *   `description`: A short, one-sentence summary of the package.
    *   `readme`: Points to your `README.md` file, which will be used as the long description on PyPI.
    *   `requires-python`: Ensure this reflects the Python versions your package supports (e.g., `>=3.8`).
    *   `license`: Specify the license (e.g., `{text = "MIT"}`).

*   **Dependencies (`[project.dependencies]`)**:
    *   List all runtime dependencies here with appropriate version specifiers. These are already properly configured in your pyproject.toml.
    *   Example: `fastapi>=0.115.0`, `click>=8.1.0`.

*   **Keywords (`[project.keywords]`)**:
    *   Add a list of keywords to help users find your package.
    *   Example: `keywords = ["llm", "chatbot", "openai", "aws", "bedrock", "chat", "api", "cli"]`

*   **Classifiers (`[project.classifiers]`)**:
    *   Provide PyPI classifiers to categorize your project. See the [PyPI classifiers list](https://pypi.org/classifiers/).
    *   Example:
        ```toml
        classifiers = [
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Topic :: Communications :: Chat",
            "Topic :: Scientific/Engineering :: Artificial Intelligence",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Utilities"
        ]
        ```

*   **Project URLs (`[project.urls]`)**:
    *   Provide links to your project's homepage, bug tracker, documentation, etc.
    *   Example:
        ```toml
        [project.urls]
        "Homepage" = "https://github.com/yourusername/open-bedrock-server"
        "Bug Tracker" = "https://github.com/yourusername/open-bedrock-server/issues"
        "Documentation" = "https://github.com/yourusername/open-bedrock-server/blob/main/README.md"
        ```

*   **CLI Scripts (`[project.scripts]`)**:
    *   Ensure this correctly defines the entry point for your CLI.
    *   Example: `bedrock-chat = "src.open_bedrock_server.cli.main:cli"` (This seems correct based on your current structure).

*   **Build System (`[build-system]`)**:
    *   Specify the build backend and its requirements.
    *   Example:
        ```toml
        [build-system]
        requires = ["setuptools>=61.0", "wheel"]
        build-backend = "setuptools.build_meta"
        ```

*   **Optional Dependencies (`[project.optional-dependencies]`)**:
    *   Move development dependencies (like `pytest`, `pytest-asyncio`, `httpx` for testing) here.
    *   Example:
        ```toml
        [project.optional-dependencies]
        dev = [
            "pytest>=7.0",
            "pytest-asyncio>=0.20",
            "httpx>=0.23", # For TestClient
            # Add other dev tools like linters, formatters if desired
        ]
        ```
    *   Users can install these with `uv pip install .[dev]`.

*   **Packaging Configuration (`[tool.setuptools.packages.find]`)**:
    *   Ensure this is configured correctly if your source code is in a subdirectory like `src/`.
    *   Example: `where = ["src"]` (This seems correct).

### Step 2: Update `README.md`

Your `README.md` file will be displayed on your PyPI project page.
*   Ensure it's well-formatted (Markdown).
*   Clearly explain what your project does, how to install it, and provide basic usage examples.
*   Remove any badges or links that might not render correctly or be relevant on PyPI.

### Step 3: Clean the Project (Optional but Recommended)

*   Review your `.gitignore` file to ensure that build artifacts (like `dist/`, `build/`, `*.egg-info/`), virtual environments (`.venv/`), and other non-source files are excluded from Git.
*   Delete any existing `dist/`, `build/`, or `*.egg-info/` directories before building to ensure a clean build.

### Step 4: Install Build Tools

Install the necessary tools for building and uploading your package:
```bash
uv pip install build twine
```
Install these in your global Python environment or a dedicated packaging virtual environment, not necessarily your project's virtual environment unless you add them to dev dependencies.

### Step 5: Build the Package

Navigate to your project's root directory (where `pyproject.toml` is located) and run:
```bash
python -m build
```
This command will create a `dist/` directory containing two files:
*   A source archive (e.g., `open_bedrock_server-0.1.0.tar.gz`)
*   A built distribution (wheel) (e.g., `open_bedrock_server-0.1.0-py3-none-any.whl`)

The wheel is a pre-compiled package format that's faster to install.

### Step 6: Test the Package Locally

Before uploading, it's crucial to test if your package installs and works correctly from the built files.
1.  Create a new, clean virtual environment:
    ```bash
    uv venv ../test_packaging_env # Create it outside your project directory
    source ../test_packaging_env/bin/activate
    ```
2.  Install your package's wheel file from the `dist/` directory (replace with your actual filename):
    ```bash
    uv pip install /path/to/your/project/dist/open_bedrock_server-0.1.0-py3-none-any.whl
    ```
3.  Test the CLI commands:
    ```bash
    bedrock-chat --help
    bedrock-chat serve --help
    # Try running the server and chat client if possible, or at least check if commands are recognized.
    ```
4.  If your package is also a library, try importing it and using some basic functionality in a Python interpreter.
5.  Deactivate and remove the test environment:
    ```bash
    deactivate
    # rm -rf ../test_packaging_env
    ```

### Step 7: Upload to TestPyPI

TestPyPI is a separate instance of PyPI for testing the distribution process without affecting the real index.

1.  **Configure Twine for TestPyPI (Optional but Recommended)**:
    You can configure `~/.pypirc` to make uploading easier:
    ```ini
    [testpypi]
    repository = https://test.pypi.org/legacy/
    username = __token__
    password = your_testpypi_api_token
    ```
    Generate an API token from your TestPyPI account settings. Using `__token__` as the username is required for API tokens.

2.  **Upload**:
    If you have `~/.pypirc` configured:
    ```bash
    twine upload --repository testpypi dist/*
    ```
    If not, you'll be prompted for your TestPyPI username and password (use `__token__` for username and the token value for password):
    ```bash
    twine upload --repository-url https://test.pypi.org/legacy/ dist/*
    ```

3.  **Verify on TestPyPI**:
    Go to `https://test.pypi.org/project/open-bedrock-server/` to see your uploaded package.

4.  **Test Installation from TestPyPI**:
    In a new, clean virtual environment:
    ```bash
    uv pip install --index-url https://test.pypi.org/simple/ open-bedrock-server
    # Or, to include pre-releases if your version is like 0.1.0a1:
    # uv pip install --index-url https://test.pypi.org/simple/ --pre open-bedrock-server
    ```
    Test the installed package as in Step 6.

### Step 8: Upload to PyPI

Once you're confident that your package works correctly and you've tested it on TestPyPI, you can upload it to the official PyPI.

1.  **Configure Twine for PyPI (Optional but Recommended)**:
    Add to your `~/.pypirc`:
    ```ini
    [pypi]
    username = __token__
    password = your_pypi_api_token
    ```
    Generate an API token from your PyPI account settings.

2.  **Upload**:
    Ensure you're uploading the correct, final version of your `dist/*` files.
    If you have `~/.pypirc` configured:
    ```bash
    twine upload dist/*
    ```
    If not, you'll be prompted (use `__token__` for username and the token value for password):
    ```bash
    twine upload --repository-url https://upload.pypi.org/legacy/ dist/*
    ```
    **Caution**: Once a version is uploaded to PyPI, it cannot be overwritten. You'll need to upload a new version if you find issues.

### Step 9: Tag a Release (Git Best Practice)

After a successful PyPI release, create a Git tag for this version:
```bash
git tag v0.1.0 # Or your current version
git push origin v0.1.0
```
This helps track which commit corresponds to which release.

### Step 10: Post-Release

*   Verify your package on its PyPI page (e.g., `https://pypi.org/project/open-bedrock-server/`).
*   Announce your new release!
*   For future updates, increment the version in `pyproject.toml` and repeat the build and upload process.

This guide provides a comprehensive overview. Remember to replace placeholders like `your-package-name`, `yourusername`, and version numbers with your actual project details. 