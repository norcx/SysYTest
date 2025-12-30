"""
测试用例发现模块
"""
import re
from pathlib import Path
from typing import List, Tuple, Optional

from .models import TestCase


class TestDiscovery:
    """测试用例发现器"""
    
    # 匹配两种格式:
    # 1. testfile1.txt, testfile2.txt (简单数字)
    # 2. testfile_000_name.txt, testfile_01_name.txt (带下划线和名称)
    _TESTFILE_PATTERN = re.compile(r'^testfile_?(\d+)(?:_(.+))?\.txt$')
    
    @staticmethod
    def _parse_testfile_name(filename: str) -> Optional[Tuple[int, str]]:
        """
        解析测试文件名，返回 (序号, 后缀名) 或 None
        
        支持格式:
        - testfile1.txt -> (1, "")
        - testfile_000_main.txt -> (0, "_main")
        - testfile_01_while_pow.txt -> (1, "_while_pow")
        """
        match = TestDiscovery._TESTFILE_PATTERN.match(filename)
        if match:
            num = int(match.group(1))
            suffix = f"_{match.group(2)}" if match.group(2) else ""
            return num, suffix
        return None
    
    @staticmethod
    def _find_input_file(test_dir: Path, num: int, suffix: str) -> Optional[Path]:
        """
        查找对应的输入文件
        
        尝试顺序:
        1. input_XXX_name.txt (带后缀)
        2. inputXXX.txt (不带下划线)
        3. input{num}.txt (简单格式)
        """
        # 格式1: input_000_main.txt
        if suffix:
            input_file = test_dir / f"input{suffix.lstrip('_')}.txt"
            if input_file.exists():
                return input_file
            # 尝试带序号的格式: input_000_main.txt
            num_str = str(num)
            input_file = test_dir / f"input_{num_str}{suffix}.txt"
            if input_file.exists():
                return input_file
            # 尝试补零格式
            for width in [2, 3]:
                padded = str(num).zfill(width)
                input_file = test_dir / f"input_{padded}{suffix}.txt"
                if input_file.exists():
                    return input_file
        
        # 格式2: input1.txt (简单格式)
        input_file = test_dir / f"input{num}.txt"
        if input_file.exists():
            return input_file
        
        return None
    
    @staticmethod
    def discover_in_dir(test_dir: Path) -> List[TestCase]:
        """
        发现目录下的所有测试用例
        
        支持格式:
        - testfile1.txt, input1.txt (简单数字)
        - testfile_000_main.txt, input_000_main.txt (带下划线和名称)
        """
        file_cases = []
        
        for testfile in test_dir.glob("testfile*.txt"):
            parsed = TestDiscovery._parse_testfile_name(testfile.name)
            if parsed:
                num, suffix = parsed
                input_file = TestDiscovery._find_input_file(test_dir, num, suffix)
                file_cases.append((num, TestCase(
                    name=testfile.name,
                    testfile=testfile,
                    input_file=input_file
                )))
        
        file_cases.sort(key=lambda x: x[0])
        return [tc for _, tc in file_cases]
    
    @staticmethod
    def discover_test_libs(testfiles_dir: Path) -> List[Path]:
        """
        发现所有测试库目录（叶子目录，即直接包含 testfile*.txt 的目录）
        支持任意深度的嵌套目录结构
        """
        test_libs = []
        
        if not testfiles_dir.exists():
            return test_libs
        
        def find_test_dirs(directory: Path):
            """递归查找包含测试文件的叶子目录"""
            has_direct_testfiles = list(directory.glob("testfile*.txt"))
            
            if has_direct_testfiles:
                test_libs.append(directory)
            else:
                for subdir in sorted(directory.iterdir()):
                    if subdir.is_dir():
                        find_test_dirs(subdir)
        
        for item in sorted(testfiles_dir.iterdir()):
            if item.is_dir():
                find_test_dirs(item)
        
        return test_libs
    
    @staticmethod
    def get_next_testfile_number(test_dir: Path) -> int:
        """获取下一个测试文件编号"""
        max_num = 0
        for testfile in test_dir.glob("testfile*.txt"):
            parsed = TestDiscovery._parse_testfile_name(testfile.name)
            if parsed:
                num, _ = parsed
                max_num = max(max_num, num)
        return max_num + 1
