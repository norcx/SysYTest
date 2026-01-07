---
name: create-sysy-testcase
description: Convert C/C++ code into Strict SysY testcases using Python automation scripts.
---

# SysY Testcase Conversion Workflow

You are an expert compiler engineer. Your goal is to convert standard C/C++ competitive programming code into **Strict SysY** (a simplified C subset) and generate valid test data.

## Non-Negotiable Grammar Rules
**Adhere to these rules strictly.** Read `references/sysy_lang_grammar.md` **only** if you encounter an obscure syntax edge case not covered here.

| Feature | Constraint | Fix / Refactor |
| :--- | :--- | :--- |
| **Prototypes** | **Implicit** | **Do NOT** write `int getint();` or `int printf(...);`. |
| **Memory / Size** | **Max 4MB Total** (MARS Limit) | **Scale Down Constants**. `1e6` $\to$ `1e4`. Total `int` elements < 500,000. |
| **Preprocessor** | **BANNED** (`#include`, `#define`, `#ifdef`) | Use `const int` for constants. Delete imports. |
| **Types** | `int`, `void` **ONLY** | No `long long`, `float`, `double`, `char`, `bool`. |
| **Pointers** | **BANNED** (`int *p`, `&x`, `*ptr`) | Pass arrays as `int a[]`. Use **return values** for scalar outputs (no `void f(int *res)`). |
| **Arrays** | **1D Arrays ONLY** | Flatten `int a[N][M]` $\to$ `int a[N*M]`. **No VLAs**. |
| **Loops** | **`for` loops ONLY**. **No declarations inside `()`** | Move vars out: `int i; for(i=0;...)`. No `do-while`. |
| **Returns** | **Non-void funcs MUST return** | Add dummy `return 0;` at end of function, **even after infinite loops**. |
| **Input** | `int getint()` **ONLY** | No `scanf`, `cin`, `getchar`. |
| **Output** | `printf` **ONLY** | Format string supports `%d` and `\n` **ONLY**. No `%c`, `%s`, `%05d`. |
| **Operators** | No Bitwise (`<<`, `>>`, `&`, `|`, `^`) | Use arithmetic: `*2`, `/2`, `%2`. Use lookup tables. |
| **Structs** | **BANNED** | Split into parallel arrays (e.g., `x[N]`, `y[N]`). |
| **Globals** | Encouraged for large arrays | Prevent stack overflow in SysY runtime, keep totol size < 4MB. |
| **Input Data** | **Strictly 1 Integer Per Line** (`in.txt`) | No spaces (`1 2`). Must be `1\n2`. Matches MIPS syscall. |

## Execution Protocol

Follow these steps sequentially.

### Step 1: Initialize

Use the helper script to create the directory and placeholder files.

```bash
python3 .codex/skills/create-sysy-testcase/scripts/init_case.py <TARGET_DIR>
```

### Step 2: Write Logic (The Intelligence Part)

Translate the source logic into Strict SysY. Focus your "thinking" here.

- **Scale Down**: If original code has `MAXN = 100000`, change it smaller to fix up to MARS's address space limit(about 4MB). Ensure logic consistency.
- **Refactor** logic to fit the constraints above (e.g., flatten 2D arrays).
- **Write** the code to `testfile.txt`.
- **Write** input data to `in.txt` (newline-separated integers only) matching your scaled-down size.

```bash
cat <<'EOF' > <TARGET_DIR>/testfile.txt
// ... your converted SysY code ...
EOF

cat <<'EOF' > <TARGET_DIR>/in.txt
// ... your input numbers ...
EOF
```

### Step 3: Compile, Run & Verify

Use the runner script. It automatically wraps your code with C headers, compiles it (gcc/clang), runs it against `in.txt`, and generates `ans.txt`.

```bash
python3 .codex/skills/create-sysy-testcase/scripts/run_case.py <TARGET_DIR>
```

### Step 4: Fix & Retry

If Step 3 reports a **COMPILE ERROR** or **RUNTIME ERROR**:

1. Read the error output.
2. Fix the logic in `testfile.txt`.
3. Rerun Step 3.

## Translation Strategy Tips
- SysY input (`in.txt`) must be **newline-separated integers**.
- If the original problem uses strings (e.g., "PUSH", "POP"), map them to integers (e.g., 1, 2) in your translation logic.
- **MIPS Compatibility Check**: `in.txt` **must not** contain spaces between numbers.
