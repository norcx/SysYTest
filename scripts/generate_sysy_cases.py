#!/usr/bin/env python3
import argparse
import asyncio
import datetime
import os
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from shutil import copy2
from typing import Iterable, Optional


@dataclass(frozen=True)
class Job:
    index: int
    total: int
    src: Path
    src_display: str
    suite_name: str
    target_dir: Path


def _iter_code_files(code_dir: Path) -> list[Path]:
    exts = {".c", ".cpp"}
    return sorted(
        [p for p in code_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts],
        key=lambda p: str(p.relative_to(code_dir)),
    )


def _has_existing_testcase(target_dir: Path) -> bool:
    return any(
        (target_dir / name).exists() for name in ("testfile.txt", "in.txt", "ans.txt")
    )


def _build_prompt(src: Path, target_dir: Path) -> str:
    return f"$create-sysy-testcase convert {src} into a strict SysY testcase in {target_dir}.\n"


def _build_isolated_prompt(*, src_code: str, out_dir: Path) -> str:
    # Embed source code inline so Codex does not need to read it from disk.
    # The skill itself should be resolved by name (e.g., from CODEX_HOME).
    return (
        "$create-sysy-testcase\n"
        "Convert the following C/C++ source into a strict SysY testcase.\n"
        f"Write all outputs into this directory: {out_dir}\n"
        "\n"
        "--- BEGIN SOURCE ---\n"
        f"{src_code}\n"
        "--- END SOURCE ---\n"
    )


def _format_ts(dt: Optional[datetime.datetime] = None) -> str:
    return (dt or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def _snapshot_target_dir(target_dir: Path) -> str:
    patterns = ("testfile*.txt", "input*.txt", "testfile.txt", "in.txt", "ans.txt")
    files: set[Path] = set()
    for pattern in patterns:
        files.update(target_dir.glob(pattern))

    if not files:
        return "(no matching files)"

    lines: list[str] = []
    for path in sorted(files, key=lambda p: p.name):
        try:
            stat = path.stat()
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
            lines.append(f"- {path.name} ({stat.st_size} bytes, mtime={_format_ts(mtime)})")
        except OSError as e:
            lines.append(f"- {path.name} (stat failed: {e})")
    return "\n".join(lines)


def _make_job_log_path(job: Job) -> Path:
    # Unique filename avoids interleaving logs if multiple runs touch the same dir.
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    return job.target_dir / f"codex_job{job.index:04d}_{ts}_pid{pid}.log"


async def _terminate_process_group(proc: asyncio.subprocess.Process, timeout_s: float) -> None:
    if proc.returncode is not None:
        return

    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
        return
    except asyncio.TimeoutError:
        pass

    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return

    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        return


async def _kill_running(running: Iterable[asyncio.subprocess.Process]) -> None:
    procs = [p for p in running if p.returncode is None]
    if not procs:
        return
    await asyncio.gather(*(_terminate_process_group(p, timeout_s=2.0) for p in procs))


async def _run_job(
    job: Job,
    *,
    root_dir: Path,
    codex_bin: str,
    sem: asyncio.Semaphore,
    running: set[asyncio.subprocess.Process],
    timeout_s: Optional[float],
    verbose: bool,
    isolate: bool,
) -> int:
    async with sem:
        tmp_root_ctx: Optional[tempfile.TemporaryDirectory] = None
        codex_root = root_dir
        out_dir = job.target_dir

        if isolate:
            tmp_root_ctx = tempfile.TemporaryDirectory(prefix="sysytest_codex_", dir=None)
            codex_root = Path(tmp_root_ctx.name)
            out_dir = codex_root
            src_code = job.src.read_text(encoding="utf-8", errors="replace")
            prompt = _build_isolated_prompt(
                src_code=src_code,
                out_dir=out_dir,
            )
            cmd = [
                codex_bin,
                "exec",
                "--skip-git-repo-check",
                "--full-auto",
                "-C",
                str(codex_root),
                "-",
            ]
        else:
            prompt = _build_prompt(job.src, job.target_dir)
            cmd = [codex_bin, "exec", "--full-auto", "-C", str(codex_root), "-"]

        job.target_dir.mkdir(parents=True, exist_ok=True)
        log_path = _make_job_log_path(job)
        start_ts = time.monotonic()
        if verbose:
            print(
                f"[{job.index}/{job.total}] START {job.src_display} -> {job.target_dir} "
                f"(log: {log_path.name})"
            )
        else:
            print(f"[{job.index}/{job.total}] START {job.src_display} (log: {log_path.name})")

        log_file = None
        proc: Optional[asyncio.subprocess.Process] = None
        try:
            log_file = open(log_path, "ab", buffering=0)
            header = (
                "=== generate_sysy_cases.py job log ===\n"
                f"start: {_format_ts()}\n"
                f"src: {job.src_display}\n"
                f"src_abs: {job.src}\n"
                f"target_dir: {job.target_dir}\n"
                f"isolate: {isolate}\n"
                f"codex_root: {codex_root}\n"
                f"out_dir: {out_dir}\n"
                f"cmd: {' '.join(cmd)}\n"
                "\n--- prompt ---\n"
                f"{prompt}"
                "\n--- pre-snapshot ---\n"
                f"{_snapshot_target_dir(out_dir if isolate else job.target_dir)}\n"
                "\n--- codex output (stdout+stderr) ---\n"
            )
            log_file.write(header.encode("utf-8", errors="replace"))

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )
        except FileNotFoundError:
            if log_file is not None:
                log_file.write(
                    (
                        "\n--- job summary ---\n"
                        f"end: {_format_ts()}\n"
                        "status: CODEx_BIN_NOT_FOUND\n"
                        f"codex_bin: {codex_bin}\n"
                        f"elapsed_s: {time.monotonic() - start_ts:.3f}\n"
                    ).encode("utf-8", errors="replace")
                )
                log_file.close()
            print(
                f"[{job.index}/{job.total}] FAIL {job.src_display} "
                f"(codex not found: {codex_bin})",
                file=sys.stderr,
            )
            return 127

        running.add(proc)
        try:
            input_bytes = prompt.encode("utf-8")
            if timeout_s is None:
                try:
                    await proc.communicate(input=input_bytes)
                except asyncio.CancelledError:
                    await _terminate_process_group(proc, timeout_s=2.0)
                    if log_file is not None:
                        log_file.write(
                            (
                                "\n--- job summary ---\n"
                                f"end: {_format_ts()}\n"
                                "status: CANCELLED\n"
                                f"elapsed_s: {time.monotonic() - start_ts:.3f}\n"
                            ).encode("utf-8", errors="replace")
                        )
                        log_file.close()
                        log_file = None
                    raise
            else:
                try:
                    await asyncio.wait_for(proc.communicate(input=input_bytes), timeout=timeout_s)
                except asyncio.TimeoutError:
                    await _terminate_process_group(proc, timeout_s=2.0)
                    print(f"[{job.index}/{job.total}] TIMEOUT {job.src_display}")
                    if log_file is not None:
                        log_file.write(
                            (
                                "\n--- job summary ---\n"
                                f"end: {_format_ts()}\n"
                                "status: TIMEOUT\n"
                                f"timeout_s: {timeout_s}\n"
                                f"elapsed_s: {time.monotonic() - start_ts:.3f}\n"
                                "\n--- post-snapshot ---\n"
                                f"{_snapshot_target_dir(out_dir if isolate else job.target_dir)}\n"
                            ).encode("utf-8", errors="replace")
                        )
                        log_file.close()
                        log_file = None
                    return 124
                except asyncio.CancelledError:
                    await _terminate_process_group(proc, timeout_s=2.0)
                    if log_file is not None:
                        log_file.write(
                            (
                                "\n--- job summary ---\n"
                                f"end: {_format_ts()}\n"
                                "status: CANCELLED\n"
                                f"elapsed_s: {time.monotonic() - start_ts:.3f}\n"
                            ).encode("utf-8", errors="replace")
                        )
                        log_file.close()
                        log_file = None
                    raise
        finally:
            if proc is not None:
                running.discard(proc)

        rc = int(proc.returncode or 0)
        if log_file is not None:
            log_file.write(
                (
                    "\n--- job summary ---\n"
                    f"end: {_format_ts()}\n"
                    f"rc: {rc}\n"
                    f"elapsed_s: {time.monotonic() - start_ts:.3f}\n"
                    "\n--- post-snapshot ---\n"
                    f"{_snapshot_target_dir(out_dir if isolate else job.target_dir)}\n"
                ).encode("utf-8", errors="replace")
            )
            log_file.close()

        if isolate and rc == 0:
            # Copy everything produced in the isolated temp dir back to target_dir.
            # Keep the temp dir empty at start; we never copy the source in.
            for path in codex_root.rglob("*"):
                rel = path.relative_to(codex_root)
                if not path.is_file():
                    continue
                if rel.parts and rel.parts[0] == "__pycache__":
                    continue
                if path.name in ("__runner.c", "__runner.exe"):
                    continue
                dest = job.target_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                copy2(path, dest)

        if tmp_root_ctx is not None:
            tmp_root_ctx.cleanup()
        if rc == 0:
            print(f"[{job.index}/{job.total}] OK {job.src_display}")
        else:
            print(f"[{job.index}/{job.total}] FAIL {job.src_display} (rc={rc})")
        return rc


async def _run_job_wrapped(
    job: Job,
    *,
    root_dir: Path,
    codex_bin: str,
    sem: asyncio.Semaphore,
    running: set[asyncio.subprocess.Process],
    timeout_s: Optional[float],
    verbose: bool,
    isolate: bool,
) -> tuple[Job, int]:
    rc = await _run_job(
        job,
        root_dir=root_dir,
        codex_bin=codex_bin,
        sem=sem,
        running=running,
        timeout_s=timeout_s,
        verbose=verbose,
        isolate=isolate,
    )
    return job, rc


async def _run_all(
    jobs: list[Job],
    *,
    root_dir: Path,
    codex_bin: str,
    concurrency: int,
    timeout_s: Optional[float],
    keep_going: bool,
    verbose: bool,
    isolate: bool,
) -> int:
    sem = asyncio.Semaphore(concurrency)
    running: set[asyncio.subprocess.Process] = set()
    tasks: list[asyncio.Task[tuple[Job, int]]] = []
    failures: list[Job] = []

    try:
        for job in jobs:
            tasks.append(
                asyncio.create_task(
                    _run_job_wrapped(
                        job,
                        root_dir=root_dir,
                        codex_bin=codex_bin,
                        sem=sem,
                        running=running,
                        timeout_s=timeout_s,
                        verbose=verbose,
                        isolate=isolate,
                    )
                )
            )

        for task in asyncio.as_completed(tasks):
            job, rc = await task
            if rc != 0:
                failures.append(job)
                if not keep_going:
                    for t in tasks:
                        t.cancel()
                    break
    finally:
        await _kill_running(running)
        await asyncio.gather(*tasks, return_exceptions=True)

    if failures:
        return 1
    return 0


def _parse_args(argv: list[str], *, root_dir: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generate_sysy_cases.py",
        description=(
            "Batch-generate SysY testcases from ./codes (recursively) using Codex + "
            "create-sysy-testcase skill."
        ),
    )
    parser.add_argument(
        "--codes",
        default=str(root_dir / "codes"),
        help="Directory to scan recursively for source files (default: ./codes)",
    )
    parser.add_argument(
        "--dest",
        default=str(root_dir / "testcases" / "generated_from_codes"),
        help=(
            "Destination root where results should live; relative subdirs under --codes "
            "are preserved to avoid name collisions (default: ./testcases/generated_from_codes)"
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip suites that already contain testfile.txt/in.txt/ans.txt",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=1,
        help="Number of concurrent Codex processes to run (default: 1)",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Do not stop other jobs after the first failure",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Per-job timeout in seconds (default: unlimited)",
    )
    parser.add_argument(
        "--isolate",
        action="store_true",
        help=(
            "Run Codex from an empty system temp directory and embed source code in the prompt; "
            "copy the generated outputs back to the destination suite directory."
        ),
    )
    parser.add_argument(
        "--codex-bin",
        default=os.environ.get("CODEX_BIN", "codex"),
        help="Codex executable (default: $CODEX_BIN or 'codex')",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print target directories as jobs start",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    root_dir = Path(__file__).resolve().parent.parent
    args = _parse_args(argv, root_dir=root_dir)

    code_dir = Path(args.codes).expanduser().resolve()
    dest_root = Path(args.dest).expanduser().resolve()
    concurrency = max(1, int(args.jobs))

    if not code_dir.is_dir():
        print(f"Codes directory {code_dir} does not exist", file=sys.stderr)
        return 1

    dest_root.mkdir(parents=True, exist_ok=True)

    code_files = _iter_code_files(code_dir)
    if not code_files:
        print(f"No .c/.cpp files found inside {code_dir}", file=sys.stderr)
        return 1

    selected: list[Job] = []
    total = len(code_files)
    for i, src in enumerate(code_files, start=1):
        rel_src = src.relative_to(code_dir)
        suite_rel = rel_src.with_suffix("")
        suite_name = str(suite_rel)
        target_dir = dest_root / suite_rel

        if args.resume and _has_existing_testcase(target_dir):
            print(
                f"[{i}/{total}] SKIP {rel_src} "
                f"(existing testcase detected in {target_dir})"
            )
            continue

        selected.append(
            Job(
                index=i,
                total=total,
                src=src,
                src_display=str(rel_src),
                suite_name=suite_name,
                target_dir=target_dir,
            )
        )

    if not selected:
        print("Nothing to do (all suites skipped).")
        return 0

    print(
        f"Running {len(selected)} job(s) with -j {concurrency} "
        f"(codes: {code_dir}, dest: {dest_root}, codex: {args.codex_bin})"
    )

    try:
        return asyncio.run(
            _run_all(
                selected,
                root_dir=root_dir,
                codex_bin=args.codex_bin,
                concurrency=concurrency,
                timeout_s=args.timeout,
                keep_going=bool(args.keep_going),
                verbose=bool(args.verbose),
                isolate=bool(args.isolate),
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted, stopping all remaining Codex sessions.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
