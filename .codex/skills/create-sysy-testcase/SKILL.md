---
name: create-sysy-testcase
description: Create SysY testcases that are 100% grammar-compliant (pure SysY syntax, for-loops only, printf-only output, newline-separated stdin) while delivering the canonical testfile/in/ans trio.
---

# SysY Testcase Maker

A testcase that drifts from the SysY grammar is useless. Treat every request as a grammar audit first and only ship when you can prove the program, inputs, and outputs would be accepted by a strict SysY parser.

## Non-Negotiable Grammar Rules
- Cross-check every construct against `references/sysy_lang_grammar.md`; if it cannot be derived from that grammar, rewrite it.
- All loops must be spelled as `for` statements—no `while`, `do while`, or disguised macros.
- All observable output must flow through `printf` with literal format strings; never call `putch`, `putint`, or custom wrappers.
- Never add manual prototypes for runtime helpers such as `getint`; the runtime library already provides them.
- `in.txt` must list each numeric token on its own line. Spaces or mixed delimiters immediately invalidate the testcase.
- Record in the testcase notes that you performed this audit; if any exception exists, fix the program instead of documenting the deviation.

## Workflow
1. **Author strictly grammatical SysY** – Port or write the program while the grammar file is open. Replace any unsupported constructs (types, control flow, IO) with SysY-compliant equivalents. Keep the code minimal and comment the covered grammar items only if it helps future audits.
2. **Scaffold the files** – Use native shell commands (e.g., `cp -R create-sysy-testcase/assets/testcase_template <target-dir>`) to clone the template directory and immediately rename/populate `testfile.txt`, `in.txt`, `ans.txt`. Ignore taxonomy concerns; just keep the trio together with no extra files.
3. **Define stdin/stdout carefully** – Write `in.txt` with newline-separated literals in the exact evaluation order. Compile and run the testcase with the toolchain available in this environment (e.g., gcc, clang, or the provided SysY compiler) to obtain the authoritative output, then store the exact `printf` result in `ans.txt`, including the trailing newline if emitted.
4. **Validate relentlessly** – Recompile with your SysY toolchain, run against `in.txt`, and `diff -u` the result with `ans.txt`. Manually re-scan `testfile.txt` to ensure only `for` loops, `printf` output, and grammar-approved constructs remain.
5. **Document verification** – Leave a short note or comment with the commands you ran and a checkbox-style reminder of the grammar audit so future maintainers know the testcase already passed the strict checks.

## Resources
- `references/sysy_lang_grammar.md` – canonical grammar used for every audit.
- `create-sysy-testcase/assets/testcase_template/` – canonical directory to copy when creating `testfile.txt`, `in.txt`, and `ans.txt` with native filesystem commands.
