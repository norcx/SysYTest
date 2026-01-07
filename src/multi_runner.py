"""
多编译器实例的编译与测试调度。

目标：在 `parallel.max_workers` 限制下，对多个 CompilerTester 实例并发运行测试用例。
"""

from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .models import TestCase, TestResult, TestStatus
from .tester import CompilerTester


CompileCallback = Callable[[CompilerTester, bool, str], None]
TestCallback = Callable[[CompilerTester, TestCase, TestResult, int, int], None]


def compile_testers(
    testers: List[CompilerTester],
    max_workers: int,
    stop_event: Optional[threading.Event] = None,
    callback: Optional[CompileCallback] = None,
) -> Dict[str, Tuple[bool, str]]:
    if not testers:
        return {}

    results: Dict[str, Tuple[bool, str]] = {}
    workers = max(1, min(int(max_workers or 1), len(testers)))

    def run_one(tester: CompilerTester) -> Tuple[CompilerTester, bool, str]:
        if stop_event and stop_event.is_set():
            return tester, False, "已停止"
        ok, msg = tester.compile_project()
        return tester, ok, msg

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_one, t) for t in testers]
        for fut in futures:
            tester, ok, msg = fut.result()
            results[tester.instance_name] = (ok, msg)
            if callback:
                callback(tester, ok, msg)

    return results


def iter_round_robin_tasks(testers: List[CompilerTester], cases: List[TestCase]) -> Iterable[Tuple[CompilerTester, TestCase]]:
    if not testers or not cases:
        return
    n = len(testers)
    for case_i, case in enumerate(cases):
        start = case_i % n
        for j in range(n):
            yield testers[(start + j) % n], case


def test_multi(
    testers: List[CompilerTester],
    cases: List[TestCase],
    max_workers: int,
    stop_event: Optional[threading.Event] = None,
    callback: Optional[TestCallback] = None,
) -> List[Tuple[str, TestCase, TestResult]]:
    """对多个编译器实例运行用例，返回 [(instance_name, case, result), ...]。"""
    if not testers or not cases:
        return []

    tasks = iter_round_robin_tasks(testers, cases)
    total = len(testers) * len(cases)
    completed = 0
    results: List[Tuple[str, TestCase, TestResult]] = []

    def run_one(tester: CompilerTester, case: TestCase) -> Tuple[str, TestCase, TestResult]:
        if stop_event and stop_event.is_set():
            return tester.instance_name, case, TestResult(TestStatus.SKIPPED, "已停止")
        worker_id = tester.allocate_worker_id(max_workers=max(1, int(max_workers or 1)))
        result = tester.test(case.testfile, case.input_file, case.expected_output_file, worker_id)
        return tester.instance_name, case, result

    workers = max(1, int(max_workers or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        in_flight: Dict[Future, Tuple[CompilerTester, TestCase]] = {}

        def submit_next():
            if stop_event and stop_event.is_set():
                return False
            try:
                tester, case = next(tasks)
            except StopIteration:
                return False
            in_flight[executor.submit(run_one, tester, case)] = (tester, case)
            return True

        for _ in range(min(workers, total)):
            if not submit_next():
                break

        while in_flight:
            done, _pending = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                tester, case = in_flight.pop(fut)
                instance_name, case_obj, result = fut.result()
                results.append((instance_name, case_obj, result))
                completed += 1
                if callback:
                    callback(tester, case_obj, result, completed, total)
                if len(in_flight) < workers:
                    submit_next()

    return results
