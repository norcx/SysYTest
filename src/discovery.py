"""
测试用例发现模块
"""
from pathlib import Path
from typing import List, Optional

from .models import TestCase


class TestDiscovery:
    """测试用例发现器"""

    _TESTFILE_NAME = "testfile.txt"
    _INPUT_NAME = "in.txt"
    _ANSWER_NAME = "ans.txt"

    @staticmethod
    def _natural_key(text: str):
        """用于路径/名称的自然排序 key（把数字段按整数排序）。"""
        parts = []
        buf = ""
        is_digit = None
        for ch in text:
            ch_is_digit = ch.isdigit()
            if is_digit is None:
                buf = ch
                is_digit = ch_is_digit
                continue
            if ch_is_digit == is_digit:
                buf += ch
                continue
            parts.append((0, int(buf)) if is_digit else (1, buf.lower()))
            buf = ch
            is_digit = ch_is_digit
        if buf:
            parts.append((0, int(buf)) if is_digit else (1, buf.lower()))
        return tuple(parts)

    @staticmethod
    def _is_case_dir(directory: Path) -> bool:
        return (directory / TestDiscovery._TESTFILE_NAME).is_file()

    @staticmethod
    def _iter_case_dirs(root_dir: Path) -> List[Path]:
        """递归查找用例目录：任意深度下直接包含 testfile.txt 的目录视为一个用例。"""
        case_dirs: List[Path] = []

        if not root_dir.exists():
            return case_dirs

        def walk(current: Path):
            if TestDiscovery._is_case_dir(current):
                case_dirs.append(current)
                return
            try:
                children = sorted(
                    (p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".")),
                    key=lambda p: TestDiscovery._natural_key(p.name),
                )
            except PermissionError:
                return
            for child in children:
                walk(child)

        walk(root_dir)
        return case_dirs

    @staticmethod
    def _has_case_in_subtree(root_dir: Path) -> bool:
        """快速判断子树内是否存在用例目录（找到第一个即返回）。"""
        if not root_dir.exists():
            return False

        def walk(current: Path) -> bool:
            if TestDiscovery._is_case_dir(current):
                return True
            try:
                for child in current.iterdir():
                    if not child.is_dir() or child.name.startswith("."):
                        continue
                    if walk(child):
                        return True
            except PermissionError:
                return False
            return False

        return walk(root_dir)
    
    @staticmethod
    def discover_in_dir(test_dir: Path) -> List[TestCase]:
        """
        发现目录（suite/lib）下的所有测试用例。

        用例目录定义：任意深度的子目录中，直接包含 `testfile.txt` 的目录。
        单个用例目录常见文件：
        - testfile.txt（必需）
        - in.txt（可选）
        - ans.txt（可选）
        """
        case_dirs = TestDiscovery._iter_case_dirs(test_dir)
        cases: List[TestCase] = []

        for case_dir in case_dirs:
            rel = case_dir.relative_to(test_dir).as_posix()
            name = test_dir.name if rel == "." else rel

            testfile = case_dir / TestDiscovery._TESTFILE_NAME
            input_file = case_dir / TestDiscovery._INPUT_NAME
            answer_file = case_dir / TestDiscovery._ANSWER_NAME

            cases.append(
                TestCase(
                    name=name,
                    testfile=testfile,
                    input_file=input_file if input_file.exists() else None,
                    expected_output_file=answer_file if answer_file.exists() else None,
                )
            )

        cases.sort(key=lambda c: TestDiscovery._natural_key(c.name))
        return cases
    
    @staticmethod
    def discover_test_libs(testcases_dir: Path) -> List[Path]:
        """
        发现可供选择的测试库（suite）目录。

        规则：
        - 默认列出 `testcases/` 下的一级子目录（若其子树内存在用例目录）
        - 若 `testcases/` 目录本身直接包含用例（或其本身就是用例目录），也会将其作为一个库返回
        """
        libs: List[Path] = []
        if not testcases_dir.exists():
            return libs

        # 若 testcases 目录本身直接承载用例，允许作为一个库选择（显示为 "."）
        try:
            direct_case_child = any(
                p.is_dir() and TestDiscovery._is_case_dir(p)
                for p in testcases_dir.iterdir()
            )
        except PermissionError:
            direct_case_child = False

        if TestDiscovery._is_case_dir(testcases_dir) or direct_case_child:
            libs.append(testcases_dir)

        for child in sorted(
            (p for p in testcases_dir.iterdir() if p.is_dir() and not p.name.startswith(".")),
            key=lambda p: TestDiscovery._natural_key(p.name),
        ):
            if TestDiscovery._has_case_in_subtree(child):
                libs.append(child)

        return libs
    
    @staticmethod
    def get_next_testfile_number(test_dir: Path) -> int:
        """获取下一个测试用例编号（用于生成 `testcaseN/` 目录）。"""
        import re

        max_num = 0
        pattern = re.compile(r"^testcase(\d+)$", re.IGNORECASE)
        if not test_dir.exists():
            return 1

        for item in test_dir.iterdir():
            if not item.is_dir():
                continue
            m = pattern.match(item.name)
            if not m:
                continue
            try:
                max_num = max(max_num, int(m.group(1)))
            except ValueError:
                continue

        return max_num + 1
