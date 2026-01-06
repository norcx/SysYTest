# Repository Guidelines

## Project Structure & Module Organization
SysYTest is invoked through `main.py`, which boots `src/cli.py`; core logic lives under `src/`, including CLI orchestration (`cli.py`), GUI components (`gui/` + `gui.py`), compiler orchestration (`tester.py`), discovery (`discovery.py`), and shared helpers (`utils.py`, `config.py`). Assets such as `Mars.jar` ship here as well. Shared configuration sits in `config.yaml`, while case data resides in `testcases/<suite>/` with paired `testfileN.txt` plus optional `inputN.txt`. Keep AI automation and agent scripts inside `src/agent/` if you extend that flow.

## Build, Test, and Development Commands
Create a virtual environment and install the lightweight deps the GUI and HTTP agent rely on: `pip install pyyaml httpx`. Run the desktop workflow with `python main.py`. For CI or headless usage, point to your compiler tree: `python main.py --project ../Compiler`. Filter workloads via repeated `--match parser` flags, and add `--show-cycle` or `--show-time` to surface performance diagnostics. Use `python main.py --help` to confirm switches after adjusting CLI arguments.

## Coding Style & Naming Conventions
All Python modules target 3.8+, follow 4-space indentation, and prefer explicit type hints and dataclasses (see `src/tester.py`). Keep module docstrings concise and place logging helpers near their call sites as in `src/cli.py`. New utilities belong under `src/utils.py` or a dedicated subpackage—avoid cluttering the repo root. Test suites use descriptive folder names (for example `testcases/loops/`) and incremental filenames (`testfile3.txt`, `input3.txt`). Keep config keys snake_case to match `config.yaml`.

## Testing Guidelines
Before submitting changes, run `python main.py --project <path>` and ensure every discovered case passes; capture failure diffs via the CLI output for triage. When adding tests, mirror the `testcases/<suite>/testfileN.txt` + `inputN.txt` layout and document the suite purpose if it is not obvious. Use `--match suite_name` while iterating to avoid rerunning the full catalog. Tune parallelism in `config.yaml` (`parallel.max_workers`) only if you also mention the new expectation in your PR. If you rely on the AI generator, record the prompt and verify the produced case with both Mars and g++ outputs.

## Commit & Pull Request Guidelines
History shows Conventional Commit messaging (`feat(testcases): Add guluor-w test case`) with lowercase scopes; continue using `feat`, `fix`, or `chore` plus the touched module or suite. Include concise English or Chinese descriptions, but keep an imperative tone. Every PR should describe what changed, how it was validated (e.g., "`python main.py --project ../Compiler` all green"), and link the tracked issue or test plan. Provide screenshots only when UI behavior changes; otherwise paste relevant CLI snippets. Avoid committing generated binaries, personal compiler sources, or secrets—update `.gitignore` instead when a new build artifact appears.

## Configuration & Security Tips
Treat `config.yaml` as environment-specific: set `compiler_project_dir`, tool paths, and timeouts locally rather than embedding organization-wide defaults. Keep sensitive API keys for the AI generator in your OS keyring or `.env` files excluded by Git; never bake them into commits. If you script automation, reference the existing accessor methods in `src/config.py` so overrides continue to respect workspace-relative paths.
