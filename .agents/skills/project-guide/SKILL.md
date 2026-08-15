---
name: project-guide
description: >-
  Generates or updates the project's technical architecture guide (GUIDE.md) at the repository root.
  Use this skill whenever the user requests to create, update, or audit GUIDE.md, or after major structural and tech stack changes.
  Fully generic and adaptive across all programming languages, project types (CLI, Web, API, Mobile, Library, Monorepo), and operating systems.
---

# Generic Project Architecture & Directory Guide Maintainer (`GUIDE.md`)

This skill defines standard operating procedures for generating and maintaining `GUIDE.md` at the project root for **any software project**. `GUIDE.md` serves as the single source of truth for a repository's system architecture, technical stack dependencies, environment requirements, directory structure, and development workflows.

> **Universal & Generic Principle**:
> This skill makes **zero assumptions** about pre-existing directories, frameworks, or client platforms (e.g. mobile, frontend, or backend). It dynamically adapts to pure CLI tools, single-package libraries, monoliths, microservices, web apps, mobile apps, or multi-tier monorepos.

---

## 1. Trigger Conditions & Objectives

Activate this skill when:
- The user requests to create, generate, update, or audit `GUIDE.md`.
- Structural changes, directory reorganizations, new modules, or dependency upgrades occur, requiring `GUIDE.md` to stay in sync.

Core Objectives:
1. **Initial Generation**: If `GUIDE.md` does **not** exist in the project root, dynamically inspect the repository and generate a comprehensive `GUIDE.md` tailored specifically to the project's ecosystem.
2. **Surgical Update**: If `GUIDE.md` **already exists**, audit it against actual repository state on disk, update stale/missing directory tree entries and dependency versions, while **preserving human context, rationale, and valuable existing descriptions**.

---

## 2. Dynamic `GUIDE.md` Structure Specification

Every generated or updated `GUIDE.md` MUST conform to the standard 5-section layout, dynamically adapted to the project's actual contents:

```markdown
# [Project Name] System Architecture & Directory Guide

[Brief single-paragraph summary of what the software does, its primary entry points, and domain purpose.]

---

## 1. System Overview & Architecture

- **Core Function & Scope**: Summary of software capabilities and operational goals.
- **System Topology Diagram**: ASCII or Mermaid diagram illustrating data flow or module interaction appropriate for the project type:
  - *CLI Tool / Library*: Input -> Parser/Config -> Engine -> Execution/Output
  - *Web App / API*: Client/Browser -> Gateway/Router -> Business Services -> DB/Storage
  - *Distributed / Monorepo*: Subsystem interaction & inter-service protocols
- **Core Subsystems / Modules**: Numbered breakdown of present architectural components (omit any non-existent tiers).

---

## 2. Environment & Technical Stack Versions

A structured markdown table listing **only the subsystems and tools that actually exist** in the repository:

| Subsystem | Technology / Component | Version Requirement / Specification |
| :--- | :--- | :--- |
| **Operating System** | Host Runtime | Cross-platform / Linux / macOS / Windows |
| **Language Runtime** | Core Runtime / Compiler | Python >=3.10 / Node.js >=18 / Rust 2021 / Go 1.22 |
| **Framework / Core** | Core Framework | FastAPI / React / Express / Tokio / Flutter |
| **Database / Storage** | Storage Layer | (Include only if database is present) |
| **Build System & Tools**| Package Manager & Builder | uv / pnpm / cargo / go build / gradle / cmake |

---

## 3. Comprehensive Directory Structure

A complete directory tree in a markdown text code block (` ```text `), displaying all root-level items and expanded core source directories with `# inline comments`.

```text
[project-name]/
├── .agents/                    # AI Agent skills, rules, and customization files
├── src/                        # Primary source code modules
│   ├── core/                   # Core business logic and algorithms
│   └── main.py                 # Application entry point
├── tests/                      # Automated test suite
├── package.json (or Cargo.toml)# Project dependencies & manifest
├── README.md                   # Primary user documentation
└── GUIDE.md                    # Technical architecture & directory guide (this file)
```

**Directory Tree Formatting Rules**:
1. Use standard tree branch characters (`├──`, `└──`, `│`).
2. Every item listed MUST include a concise `# inline comment` explaining its purpose.
3. **Strict Single-Item Rule**: Every tree line (`├──`, `└──`) MUST represent exactly one file or directory. Do not combine multiple files on a single line using slashes or commas (e.g., write `adb.exe` and `AdbWinApi.dll` on separate lines).
4. Annotate non-tracked or generated items explicitly (e.g. `(git-ignored)`, `(build artifact)`).
5. Collapse external or heavy subtrees into single summary lines (e.g. `├── node_modules/ # Dependencies (git-ignored)`).
6. Filter out temporary & noise files (`.git`, `__pycache__`, `.venv`, `target`, `dist`, `.DS_Store`).

---

## 4. Deep Dives: Core Subsystems / Modules

(Detailed technical descriptions of key source modules, internal APIs, configuration schemas, or protocols present in the project.)

---

## 5. Build, Development & Execution Workflows

- **Environment Setup**: Dependency installation commands (`npm install`, `pip install -r ...`, `cargo build`, etc.).
- **Development Execution**: Command to launch local dev server, run CLI, or execute entry points.
- **Production Build & Packaging**: Build, bundle, or compile commands.
- **Testing & Quality Assurance**: Test runner execution commands (`pytest`, `npm test`, `cargo test`, `go test`).
```

---

## 3. Execution Workflow

### Step 1: Dynamic Discovery & Ecosystem Analysis

1. Check if `./GUIDE.md` exists at the project root.
2. Inspect root configuration files to identify the language ecosystem, package manager, and dependencies:
   - **Python**: `pyproject.toml`, `requirements.txt`, `Pipfile`, `setup.py`
   - **JavaScript / TypeScript**: `package.json`, `pnpm-lock.yaml`, `yarn.lock`
   - **Rust**: `Cargo.toml`
   - **Go**: `go.mod`
   - **Java / Kotlin**: `pom.xml`, `build.gradle`, `build.gradle.kts`
   - **C / C++**: `CMakeLists.txt`, `Makefile`
   - **C# / .NET**: `*.csproj`, `*.sln`
   - **Flutter / Dart**: `pubspec.yaml`
   - **Ruby / PHP**: `Gemfile`, `composer.json`
3. Scan actual directory tree to determine present modules (CLI, `src/`, `lib/`, `pkg/`, `cmd/`, `frontend/`, `backend/`, `docs/`, etc.). Do **not** expect or mandate any specific directory layout.

---

### Step 2: Generation vs Update Logic

#### Case A: `GUIDE.md` Does NOT Exist (Generate New)

1. **Synthesize Architecture**: Map real source modules and entry points into Section 1 with an appropriate ASCII/Mermaid diagram.
2. **Build Tech Stack Table**: Include rows *only* for technologies present in the manifest files.
3. **Construct Directory Tree**: Run the tree generator helper script if Python is available:
   `python .agents/skills/project-guide/scripts/generate_guide_tree.py`
   Or list actual root items and expanded source subdirectories formatted with `├──`/`└──` and `# comments`.
4. **Detail Workflows**: Document real setup, run, build, and test commands based on the detected build system.
5. **Write File**: Output `./GUIDE.md` using `write_to_file`.

#### Case B: `GUIDE.md` DOES Exist (Update Existing)

1. **Audit Tree Discrepancies**:
   - Run verification script if Python is available:
     `python .agents/skills/project-guide/scripts/check_guide_tree.py`
   - Or manually compare `GUIDE.md` Section 3 tree against disk files.
   - Detect:
     - **Stale Entries**: Files in `GUIDE.md` that have been deleted from disk.
     - **Missing Entries**: Newly created files/dirs missing from `GUIDE.md`.
     - **Annotation Conflicts**: Items marked `(git-ignored)` that are actually tracked by git.
2. **Audit Environment & Dependencies**: Update Section 2 table if manifest versions changed.
3. **Audit System Architecture**: Update Section 1 & Deep Dives if core modules or entry points changed.
4. **Perform Surgical Update**: Update changed sections while **strictly preserving existing human rationale, architectural decisions, and detailed comments**.

---

## 4. Verification Checklist

- [ ] `GUIDE.md` is at project root (`./GUIDE.md`).
- [ ] Section 1 topology and subsystems accurately reflect the actual project type (CLI, Web, Monorepo, Library, etc.).
- [ ] Section 2 tech stack table contains only relevant rows matching project manifest files.
- [ ] Section 3 directory tree covers all top-level non-noise items with `# comments`.
- [ ] Tree uses correct `├──`, `└──`, `│` formatting with zero stale deleted paths.
- [ ] Tree verification script runs clean (`python .agents/skills/project-guide/scripts/check_guide_tree.py`).
