# BlazeLang-PY (v2.1 Legacy Reference Implementation)

**Pure Python Open-Source Implementation of the BlazeLang Environment**

Developer & Studio: **ShortCodeGuy Studio**  
Official Website: [shortcodeguystudio.netlify.app](https://shortcodeguystudio.netlify.app)  
Flagship C++ Runtime: [blazelang.web.app](https://blazelang.web.app)

---

## Overview

BlazeLang-PY (v2.1) is the official open-source legacy Python reference implementation of **BlazeLang**. Designed for readability, architectural research, and educational exploration, it provides a clean, fully functional parser, lexer, and AST execution engine written in standard Python.

While modern production versions of BlazeLang (v2.5+) are driven by a proprietary high-speed C++ native core, **BlazeLang-PY (v2.1)** serves as the open reference edition for developers interested in programming language design, AST evaluation, and custom tool extensions.

---

## Performance Benchmark

Despite being implemented in pure Python, BlazeLang-PY includes aggressive AST evaluation optimizations:

- **AST Evaluation Benchmark**: Executes **1 Billion iterations in ~3 to 4 seconds**.
- **Low Memory Overhead**: Minimal memory allocation during loop execution and scope resolution.

---

## Architecture & Repository Structure

```text
BlazeLang-PY/
├── main.py              # CLI Entrypoint & Execution Loop
├── benchmarks.py        # Performance profiling & loop iteration benchmark suite
├── blazelang/           # Core Lexer, Parser, AST Nodes, and Interpreter Engine
├── extension/           # VS Code Syntax Highlighting Extension
├── tests/               # Automated test suites
├── verify_parity.blz    # Feature verification script (.blz)
├── test_map.blz         # Map data structure test (.blz)
└── test_ref.blz         # Variable reference test (.blz)
```

---

## Quick Start

### 1. Requirements
- Python 3.10 or higher

### 2. Running a BlazeLang Script
To execute a `.blz` script using the Python reference interpreter:

```bash
python main.py verify_parity.blz
```

### 3. Running Benchmarks
To run the performance profiling suite:

```bash
python benchmarks.py
```

---

## VS Code Integration

This repository includes the official VS Code syntax highlighting extension for `.blz` files located in the `extension/` directory.

---

## Open Source License

Distributed under the MIT License. See `LICENSE` for details.

Developed by **Rohit Raj (ShortCodeGuy)** — [ShortCodeGuy Studio](https://shortcodeguystudio.netlify.app)
