---
name: code-quality-audit
description: Use when auditing code quality, conducting code reviews, or verifying codebase compliance across 9 core dimensions (Functionality, Readability, Maintainability, Extensibility, Robustness, Performance, Security, UI/UX, Testability/Docs) for any programming language or project ecosystem.
---

# Code Quality Audit & Review Standard

This skill defines a comprehensive, multi-language, systematic code quality review standard across 9 core dimensions. Use this skill to evaluate pull requests, commits, or entire codebases objectively across any tech stack.

## 0. General Conventions & Severity Framework

### Severity Levels
- **[B] Blocker**: Must be fixed immediately. Blocks merge/release or causes system instability, security breaches, data corruption, or loop divergence.
- **[M] Major**: Should be fixed. Introduces architectural flaws, potential runtime bugs, high maintenance overhead, or violates core engineering standards.
- **[m] Minor**: Suggestion or optimization. Minor style inconsistencies, non-critical refactoring opportunities, or documentation enhancements.

### AI Verification Modality
- **{Static}**: Verifiable solely by reading source code, configuration files, or AST analysis.
- **{Dynamic}**: Requires running automated tests, builds, linters, profilers, or security scanners.
- **{Manual}**: Requires human-in-the-loop judgment, business domain context, or product requirement alignment.

### Mandatory Audit Output Format
For every audit cycle, evaluate and report each item using the exact format below:
```markdown
[Item ID] + [PASS / FAIL / N/A] + [Severity] + [Evidence (File:LineNo or Command Output)] + [Explanation & Remediation Suggestion]
```

### Multi-Language Adaptation Guidance
When applying these rules, adapt tool chains, libraries, and idioms to the specific project ecosystem:
- **Python**: `pytest`, `ruff`/`flake8`/`black`/`mypy`, `pip-audit`, SQLAlchemy/Django ORM, Loguru/logging.
- **JavaScript / TypeScript**: `jest`/`vitest`/`mocha`, `eslint`/`prettier`/`tsc`, `npm audit`/`snyk`/`pnpm audit`, Prisma/TypeORM/parameterized queries, React/Vue/Angular/DOM.
- **Go**: `go test`, `golangci-lint`/`gofmt`, `govulncheck`, `database/sql` prepared statements, `slog`/`zap`/`zerolog`.
- **Java / Kotlin**: `JUnit`/`TestNG`, `Checkstyle`/`SpotBugs`/`ktlint`/`Spotless`, `OWASP Dependency-Check`/`Snyk`, JPA/Hibernate/PreparedStatement, SLF4J/Logback.
- **Rust**: `cargo test`, `clippy`/`rustfmt`, `cargo audit`, `sqlx`/`diesel`, `tracing`/`log`.
- **C / C++**: `GoogleTest`/`Catch2`, `clang-tidy`/`clang-format`, Valgrind/AddressSanitizer, prepared statements in DB client libs.
- **C# / .NET**: `xUnit`/`NUnit`, `Roslyn Analyzers`/`dotnet format`, `dotnet list package --vulnerable`, Entity Framework Core/Dapper.

---

## 1. Functional Correctness

- **1.1 [B]{Dynamic} Test Suite Passage**: All unit, integration, and end-to-end tests covering critical business paths must pass with exit code `0`.
- **1.2 [B]{Static} Critical Boundary & Edge Case Coverage**: Explicitly handle and test null/undefined/nil/None values, zero values, empty collections, extreme/max-length inputs, concurrency/race conditions, and authorization boundaries.
- **1.3 [M]{Static} Closed-Loop Business Logic**: State transitions across modules, services, or workflows must form a complete closed loop (e.g., "Order -> Pay -> Fulfill -> Complete/Cancel") with no orphaned states, deadlocks, or unhandled intermediate failures.
- **1.4 [M]{Dynamic} Asynchronous & Network Resilience**: Network requests, I/O operations, and inter-service calls must configure explicit timeouts, retry policies with exponential backoff, and circuit breakers/fallbacks to prevent cascading failures during network instability.

---

## 2. Readability

- **2.1 [M]{Static} Meaningful & Intention-Revealing Naming**: Avoid meaningless or ambiguous names (e.g., `data1`, `tmp`, `flag`, `obj`, `ret`, `val`). Boolean variables and predicates must start with prefixes like `is`, `has`, `can`, `should`, or `will`.
- **2.2 [M]{Static} Complexity & Structural Limits**: Functions/methods must be $\le 50$ lines, nesting depth $\le 3$ levels, and parameter count $\le 5$ (encapsulate excess parameters into parameter objects, structs, or data classes; split oversized functions).
- **2.3 [m]{Static} High-Value Comments**: Comments must explain *Why* (business rationale, design trade-offs, edge case handling, or external workarounds/hacks) rather than *What* the syntax does. Complex algorithms and non-obvious business rules require clear explanatory comments.
- **2.4 [m]{Static} Code Style & Lint Compliance**: Strictly adhere to ecosystem-standard formatting and linting tools (`ESLint`, `Prettier`, `Ruff`, `Black`, `Clippy`, `golangci-lint`, `Checkstyle`). Zero linter errors or unaddressed warnings allowed.

---

## 3. Maintainability

- **3.1 [B]{Static} Zero Hardcoding**: Magic numbers, hardcoded URLs, file paths, API keys, credentials, environment-specific configs, and user-facing text strings must be extracted into named constants, configuration files, environment variables, or i18n resource bundles.
- **3.2 [M]{Static} High Cohesion & Low Coupling**: Adhere to the Single Responsibility Principle (SRP). Modules/classes must communicate via well-defined interfaces without architectural layering violations, tight coupling, or "inappropriate intimacy" (e.g., directly modifying internal private state of another class).
- **3.3 [M]{Static} DRY (Don't Repeat Yourself)**: Code duplication rate must be $\le 5\%$. Repeated logic across files must be abstracted into shared utility functions, custom Hooks, base classes, or reusable components.
- **3.4 [m]{Static} Cyclomatic Complexity Control**: The cyclomatic complexity of any individual function/method must be $\le 15$. Functions exceeding this threshold must be refactored using polymorphism, strategy patterns, table-driven methods, or early returns.
- **3.5 [m]{Static} Technical Debt Tracking**: All `TODO`, `FIXME`, or `XXX` comments must include an assigned owner and a direct reference to a tracking ticket or issue ID (e.g., `// TODO(username, #1234): ...`). Untracked, anonymous technical debt markers are prohibited.

---

## 4. Extensibility

- **4.1 [M]{Static} Open-Closed Principle (OCP)**: Core business logic must be open for extension but closed for modification. New features or variations should be implemented via extension points (e.g., Strategy pattern, Factory pattern, plugins, middleware, hooks) rather than modifying core conditional branches (`if/else` or `switch/case` chains).
- **4.2 [M]{Static} Dependency Inversion Principle (DIP)**: High-level modules and core domain logic must depend on abstractions (interfaces, protocols, abstract classes, traits) rather than concrete implementations, enabling seamless dependency injection, mocking in tests, and implementation swapping.
- **4.3 [m]{Static} Configuration-Driven Architecture**: Volatile business rules (e.g., approval workflows, role-based access control matrices, validation rules, routing tables, feature toggles) should be externalized into declarative configurations or data dictionaries rather than hardcoded in procedural logic.

---

## 5. Robustness & Error Handling

- **5.1 [B]{Static} Explicit Exception Handling & Fallbacks**: All I/O, network communications, file operations, serialization/deserialization, and type conversions must be wrapped in explicit exception handling or error-return checking. Silent failure swallowing (e.g., empty `catch` blocks, `except Exception: pass`, or ignoring returned error codes) is strictly prohibited.
- **5.2 [B]{Static} Input/Output Validation & Fail-Fast**: User inputs, API payloads, and third-party service responses must undergo strict type, length, range, and format validation and sanitization at system boundaries. Fail fast with clear, actionable, structured error messages upon encountering invalid data.
- **5.3 [M]{Static} Idempotency of State Transitions**: Critical write operations, mutations, and state transitions must be designed for idempotency. Repeating the same request (due to retries, double clicks, or network timeouts) must not cause duplicate records, dirty data, or inconsistent state.
- **5.4 [M]{Dynamic} Structured Logging & Traceability**: Key operational paths and error states must emit structured logs (JSON or key-value format) including unique request/trace identifiers (`traceId`, `correlationId`). **Never log sensitive data** (passwords, tokens, API keys, PII, credit card numbers, or cryptographic secrets).

---

## 6. Performance

- **6.1 [M]{Static} Algorithmic & I/O Efficiency**: Eliminate inefficient loops and redundant operations: no database queries, file I/O, or network calls inside loops; pre-compile regular expressions and reuse heavy objects; ensure dynamic list renderings in UI frameworks use stable, unique keys; use virtual scrolling or pagination for large data sets.
- **6.2 [M]{Dynamic} Latency & Throughput SLAs**: Critical endpoints and UI interactions must meet SLA thresholds: backend API response times $\le 500\text{ms}$ (for standard CRUD/transactional operations); Web/GUI initial page load and interactive feedback $\le 2\text{s}$.
- **6.3 [m]{Dynamic} Zero Resource & Memory Leaks**: Timers, event listeners, WebSocket subscriptions, database connections, file handles, and background threads must be explicitly disposed, closed, or unregistered during component unmounting, context teardown, or application shutdown.
- **6.4 [m]{Static} Lazy Loading & Code Splitting**: Heavy UI components, large images/media, non-critical stylesheets, and third-party SDKs should be loaded on demand via lazy loading, dynamic imports (`import()`), or code splitting to optimize bundle size and initial startup time.

---

## 7. Security

- **7.1 [B]{Static} XSS & Injection Prevention**: Never concatenate untrusted user input directly into HTML strings or DOM rendering APIs (`v-html`, `innerHTML`, `dangerouslySetInnerHTML`, `document.write`). Always use context-aware auto-escaping or sanitize templates.
- **7.2 [B]{Static} SQL & Command Injection Prevention**: All database interactions must use parameterized queries, prepared statements, or secure ORM query builders. Never construct SQL queries, system commands, or shell scripts via string interpolation/concatenation with external inputs.
- **7.3 [B]{Static} Secrets Management**: Secrets (API keys, private keys, database passwords, OAuth tokens, JWT secrets) must never be hardcoded in source files, checked into version control, or logged. Inject secrets via environment variables, secret vaults (e.g., HashiCorp Vault, AWS Secrets Manager), or secure configuration providers.
- **7.4 [M]{Static} Backend Authorization Enforcement**: Security permissions, access control, and tenant isolation must be rigorously enforced on the server/backend side. Frontend UI element hiding (e.g., hiding buttons or disabling menu items) is solely for UX optimization and never constitutes a security barrier.
- **7.5 [m]{Static} Clean Dependency Vulnerability Scan**: All direct and transitive project dependencies must pass vulnerability scanning (`npm audit`, `pip-audit`, `cargo audit`, `govulncheck`, `dotnet list package --vulnerable`, `OWASP Dependency-Check`) with zero known high- or critical-severity CVEs.

---

## 8. UI/UX & Interaction Experience

- **8.1 [M]{Static} Complete Four-State UI Handling**: All asynchronous UI components, data tables, and data-fetching views must explicitly handle and design for four essential states: **Loading** (skeleton screens or spinners), **Success** (rendered data), **Error** (clear failure messages with retry action), and **Empty** (friendly zero-data state with guidance).
- **8.2 [M]{Static} Double-Submit Protection**: Form submissions and critical action buttons must implement double-click protection (e.g., immediately disabling the button upon click, showing a loading indicator, or applying debouncing/throttling).
- **8.3 [m]{Static} Responsive & Touch-Friendly Layouts**: Mobile and responsive layouts must prevent unintended horizontal scrolling. Interactive touch targets (buttons, links, toggles) on touch-enabled devices must be at least $44\text{px} \times 44\text{px}$.
- **8.4 [m]{Static} Accessibility (a11y) & WCAG Compliance**: Text-to-background visual contrast ratio must meet or exceed WCAG AA standards ($\ge 4.5:1$ for normal text). Critical status indicators (success, warning, error) must use icons, labels, or patterns in addition to color to accommodate color-vision deficiencies.
- **8.5 [m]{Static} Actionable Error Messaging**: User-facing error notifications must be constructive and actionable—clearly explaining *what went wrong* and *how the user can resolve it*—rather than displaying cryptic error codes, raw HTTP statuses, or system stack traces.

---

## 9. Testability & Documentation

- **9.1 [M]{Static} Pure Functions & Side-Effect Isolation**: Core business logic and calculations should be structured as pure functions without side effects. External dependencies (database access, time providers, network clients, file systems) must be isolated and passed in via Dependency Injection (DI) to facilitate unit testing and mocking.
- **9.2 [M]{Dynamic} Test Coverage Thresholds**: Automated unit test coverage must achieve $\ge 80\%$ overall codebase coverage, with $100\%$ branch and line coverage for critical business domain logic, financial calculations, and security authentication/authorization paths.
- **9.3 [m]{Static} API & Component Documentation**: All exported public APIs, classes, interfaces, modules, and shared UI components must include standard docstrings/JSDoc/Rustdoc/GoDoc comments explaining purpose, parameters, return values, and exceptions, maintaining $\ge 95\%$ documentation coverage.
- **9.4 [m]{Static} Project Onboarding & Architecture Docs**: The project root `README.md` must provide clear, step-by-step instructions for local setup, dependency installation, build commands, and test execution. Architectural decisions, system diagrams, and design changes must be documented and synchronized in an `/architecture` or `/docs` folder.
