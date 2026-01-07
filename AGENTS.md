# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: entry point (CLI or Tkinter GUI).
- `src/`: framework code — CLI (`src/cli.py`), GUI (`src/gui/`), runner (`src/tester.py`), testcase discovery (`src/discovery.py`), config (`src/config.py`), shared models/utils.
- `config.yaml`: local tool paths, timeouts, parallelism, and GUI settings.
- `testcases/`: testcase libraries, organized by suite folders.
- `scripts/`: contributor utilities (e.g. batch generation helpers).

Testcases are organized as nested suites; a *leaf* directory containing `testfile.txt` is treated as one case. Each case directory typically contains:
- `testfile.txt`: SysY source
- `in.txt`: stdin (optional)
- `ans.txt`: expected stdout (optional; some runners may still use g++ as reference until `src/` is updated)

## Build, Test, and Development Commands
- Install deps (GUI + agent): `python3 -m pip install pyyaml httpx`
- Run GUI: `python3 main.py`
- Run headless CLI: `python3 main.py --project ../Compiler`
- Filter cases: `python3 main.py --project ../Compiler --match loop --match recursion`
- Performance extras: `--show-time`, `--show-cycle`
- Optional generator: `python3 scripts/generate_sysy_cases.py --help`

The runner compares your compiler’s Mars output against a g++ reference; ensure `java` and `g++` are available (configure via `config.yaml` if not on `PATH`).

## Coding Style & Naming Conventions
- Python: 4-space indentation, `snake_case` for functions/vars, `PascalCase` for classes; keep type hints consistent with existing modules.
- Keep repo root minimal; add new framework code under `src/` and suite data under `testcases/`.
- Do not commit build outputs or secrets; `.tmp/` and `agent_config.json` are intentionally gitignored.

## Testing Guidelines
- “Tests” are the suites in `testcases/`; validate changes with `python3 main.py --project <compiler-path>`.
- While iterating, use `--match <substring>` to avoid rerunning the full catalog.
- For compile-only checks (no Mars/g++), add a `compile_only` marker file in the case directory.

## Commit & Pull Request Guidelines
- Use Conventional Commits as in history: `feat(testcases): add more testcases`, `fix(tester): ...`.
- PRs should include: what changed, validation command output (e.g. `python3 main.py --project ...`), and screenshots only for GUI changes.
