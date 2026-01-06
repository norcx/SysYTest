# SysYTest · SysY Compiler Test Framework

SysYTest is a multi-modal test harness for SysY compiler projects. It ships with an opinionated GUI, a scriptable CLI, and an AI-assisted test authoring experience so that compiler authors can validate Java/C/C++ implementations against an executable reference (g++ + Mars). The framework manages compilation, execution, diffing, and reporting while keeping project-specific configuration in one place.

## Key Capabilities
- **One-click regression**: Build your compiler and replay every suite in `testcases/` with colored PASS/FAIL output.
- **Headless CI/CLI mode**: `python main.py --project <path>` compiles, filters, and runs cases on build servers.
- **GUI productivity**: Tabs for running tests, editing suites, and invoking the AI agent without leaving Tkinter.
- **Multi-language compiler support**: Java (jar bundling) plus C/C++ (CMake or manual g++ pipelines) with language autodetect from `config.json`.
- **Parallel execution & metrics**: Thread pool + per-case cycle/time stats derived from Mars and the weighted instruction rules in `config.yaml`.
- **AI-assisted test generation**: The Agent tab talks to MCP tools to draft SysY programs, run them through your compiler, and save curated cases.

## Architecture Overview
The project is organized as a thin launcher (`main.py`) that delegates to modules inside `src/`:

| Component | Location | Responsibility |
| --- | --- | --- |
| CLI entry | `src/cli.py` | Argument parsing, ASCII dashboard, orchestration of compiler compile/run loop. |
| GUI shell | `src/gui/app.py`, `src/gui/test_tab.py`, `src/gui/editor_tab.py`, `src/gui/agent_tab.py` | Tkinter-based workspace covering run, edit, and AI flows. |
| Tester core | `src/tester.py` | Detects compiler language, performs build (javac/jar or g++/CMake), runs Mars + g++, diffs outputs, tracks telemetry. |
| Discovery | `src/discovery.py` | Maps `testcases/<suite>/` layout into ordered `TestCase` objects and optional `inputN.txt`. |
| Config | `src/config.py` | Typed accessors (timeouts, tool paths, fonts) loaded from `config.yaml`. |
| Models/utils | `src/models.py`, `src/utils.py` | Shared dataclasses plus helpers for safe file access, diffing, etc. |
| AI Agent | `src/agent/` | HTTP client + local MCP tool server powering autonomous SysY test drafting.

**Execution flow**: CLI/GUI → `CompilerTester` compiles your project → each test case produces SysY source + input → tester invokes your compiler → Mars executes emitted MIPS → g++ runs the SysY reference implementation → outputs are compared and reported back to the UI/logs.

## Repository Structure
```
SysYTest/
├── main.py               # Unified entry point (CLI or GUI)
├── config.yaml           # Workspace overrides for tool paths, timeouts, fonts
├── src/                  # Framework code (CLI/GUI/test runner/agent)
├── testcases/            # Official and community suites (testfileN.txt + inputN.txt)
├── AGENTS.md             # Contributor workflow guide
└── README.md             # You are here
```

## Installation
1. **Prerequisites**: Python 3.8+, JDK 8+ (javac/jar), g++ (for expected output), optional CMake (C/C++ projects), and Mars.jar (bundled under `src/`).
2. **Python deps**: `pip install pyyaml httpx` (GUI + Agent rely on them; the CLI can run without httpx if you skip the Agent tab).
3. **Link compiler project**: Point `compiler_project_dir` in `config.yaml` to your SysY compiler repo (default `../Compiler`). Ensure that repo exposes `src/config.json` specifying `{"programming language": "java"|"c"|"cpp", "object code": "mips"}`.

## Running the Framework
### GUI Mode
```bash
python main.py
```
- **Test tab**: Select your compiler directory, compile once, choose suites in the tree, and run selected/all cases. Toggle `show cycle/time` to inspect performance.
- **Editor tab**: Author new `testfileN.txt` and `inputN.txt` pairs, leveraging auto-numbering from `TestDiscovery`.
- **Agent tab**: Configure API base/model/key, describe the scenario, let the LLM produce SysY code, auto-run it through your compiler, and save into a suite.

### CLI / CI Mode
```bash
python main.py --project ../Compiler            # Compile + run every test suite
python main.py --project ../Compiler --match loop --match recursion
python main.py --project ../Compiler --show-cycle --show-time
```
Use `--match` multiple times to focus on subsets. CLI output prints PASS/FAIL plus detailed diffs, including actual/expected text blocks for failures.

## Test Libraries
- Tests live under `testcases/<suite>/` using `testfileN.txt` for SysY source and optional `inputN.txt` for stdin (each line one integer).
- Suites can nest arbitrarily; discovery walks the tree and treats the deepest directory containing `testfile*.txt` as a library.
- When contributing, include README notes (or describe in PR) clarifying coverage focus.

## Configuration Highlights (`config.yaml`)
- `compiler_project_dir`: relative or absolute path to your compiler repo.
- `mars_jar`: overrides the bundled Mars build.
- `tools`: point to specific `jdk_home`, `gcc_path`, or `cmake_path` if they are not on PATH.
- `timeout`: tune compile/runtime guards (seconds).
- `parallel.max_workers`: adjust concurrency to match CPU cores; each worker gets its own `.tmp/worker_<id>` sandbox.
- `instruction_weights`: control weighted cycle reporting for Mars metrics.
- `gui.font_family`: priority-ordered list of monospace fonts for Tkinter.

## Development & Contribution Workflow
1. Fork and clone, then create a topic branch (e.g., `feat/testcases-add-loop-suite`).
2. Update or add suites under `testcases/`, framework code in `src/`, or docs.
3. Run `python main.py --project <path>` (headless) or the GUI to ensure all suites pass.
4. Format code with 4-space indentation and add comments only for non-obvious logic.
5. Commit using Conventional Commit style (`feat(cli): support cycle flag`), push, and open a PR describing motivation, coverage, and validation commands. Screenshots/log excerpts are helpful when UI or CLI output changes.

## Troubleshooting
- **`java/javac not found`**: Set `tools.jdk_home` to your JDK installation or extend PATH.
- **g++ compilation failures**: Install GCC/MinGW and optionally set `tools.gcc_path` to the executable.
- **Slow or stuck tests**: Lower or raise `parallel.max_workers` and confirm that antivirus excludes the `.tmp/` directory to prevent scans of generated binaries.
- **Mars timeouts**: Increase `timeout.mars` or audit your compiler for infinite loops.
- **Agent tab errors**: Ensure `httpx` is installed and that API credentials are configured; logs print the HTTP error message directly in the chat transcript.

Happy hacking, and feel free to open issues or PRs with ideas for new suites, UI polish, or agent integrations!
