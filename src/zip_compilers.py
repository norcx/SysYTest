"""
Zip 编译器实例发现与解包。

一个编译器实例对应 zip_dir 下的一个 .zip 文件，实例名称默认取 zip 文件名（不含扩展名）。

解包会写入到调用方提供的临时目录中（建议为 `<repo>/.tmp/compilers/`），并带缓存：
- zip 文件未变化时复用已解包目录
- zip 文件变化时自动重新解包到新的目录
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_ZIP_META_FILE = ".zip_meta.json"
_IGNORED_PREFIXES = ("__MACOSX/",)
_IGNORED_BASENAMES = {".ds_store"}


@dataclass(frozen=True)
class ZipCompilerInstance:
    """zip 编译器实例元信息（不含解包后的路径）。"""

    name: str
    zip_path: Path
    valid: bool
    reason: str = ""

    language: Optional[str] = None
    object_code: Optional[str] = None

    # config.json 在 zip 内的路径（用于确定项目根目录）
    config_path_in_zip: Optional[str] = None
    # 项目根目录在 zip 内的前缀（"" 表示 zip 根）
    project_root_in_zip: str = ""


def _safe_name(name: str) -> str:
    name = name.strip()
    if not name:
        return "compiler"
    return re.sub(r"[^0-9A-Za-z._-]+", "_", name)


def _zip_fingerprint(zip_path: Path) -> str:
    st = zip_path.stat()
    raw = f"{zip_path.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8", errors="ignore")
    return hashlib.md5(raw).hexdigest()[:12]


def _should_ignore_zip_entry(filename: str) -> bool:
    norm = filename.replace("\\", "/")
    if not norm or norm.endswith("/"):
        return True
    if any(norm.startswith(p) for p in _IGNORED_PREFIXES):
        return True
    base = norm.rsplit("/", 1)[-1].lower()
    if base in _IGNORED_BASENAMES:
        return True
    return False


def _find_config_json_path(zf: zipfile.ZipFile) -> Optional[str]:
    candidates: List[str] = []
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if _should_ignore_zip_entry(name):
            continue
        if name.lower().endswith("/config.json"):
            candidates.append(name)
        elif name.lower() == "config.json":
            candidates.append(name)
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p.count("/"), len(p)))
    return candidates[0]


def _read_json_from_zip(zf: zipfile.ZipFile, path_in_zip: str) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        with zf.open(path_in_zip, "r") as fp:
            raw = fp.read()
        data = json.loads(raw.decode("utf-8", errors="replace"))
        if not isinstance(data, dict):
            return None, "config.json 不是 JSON 对象"
        return data, ""
    except KeyError:
        return None, "zip 中未找到 config.json"
    except json.JSONDecodeError as e:
        return None, f"config.json JSON 解析失败: {e}"
    except Exception as e:
        return None, f"读取 config.json 失败: {e}"


def discover_zip_compilers(zip_dir: Path, recursive: bool = False) -> List[ZipCompilerInstance]:
    """发现 zip_dir 下的 .zip 编译器实例。

    Args:
        zip_dir: 根目录。
        recursive: 是否递归扫描子目录（用于 GUI 中 zip_dir 下按组/班级分层存放的情况）。
    """
    zip_dir = Path(zip_dir)
    if not zip_dir.exists() or not zip_dir.is_dir():
        return []

    instances: List[ZipCompilerInstance] = []
    if recursive:
        zip_files = [p for p in zip_dir.rglob("*.zip") if p.is_file()]
        key = lambda p: str(p.relative_to(zip_dir)).lower()
    else:
        zip_files = [p for p in zip_dir.iterdir() if p.is_file() and p.suffix.lower() == ".zip"]
        key = lambda p: p.name.lower()

    for zip_path in sorted(zip_files, key=key):
        if recursive:
            # 递归扫描时用相对路径作为实例名，避免子目录中同名 zip 冲突。
            name = zip_path.relative_to(zip_dir).with_suffix("").as_posix()
        else:
            name = zip_path.stem
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                config_path = _find_config_json_path(zf)
                if not config_path:
                    instances.append(
                        ZipCompilerInstance(
                            name=name,
                            zip_path=zip_path,
                            valid=False,
                            reason="缺少 config.json",
                        )
                    )
                    continue

                config, err = _read_json_from_zip(zf, config_path)
                if not config:
                    instances.append(
                        ZipCompilerInstance(
                            name=name,
                            zip_path=zip_path,
                            valid=False,
                            reason=err or "config.json 无效",
                            config_path_in_zip=config_path,
                            project_root_in_zip=str(Path(config_path).parent).replace("\\", "/").rstrip("/"),
                        )
                    )
                    continue

                lang = str(config.get("programming language", "")).strip().lower() or None
                obj = str(config.get("object code", "")).strip().lower() or None
                root = str(Path(config_path).parent).replace("\\", "/").rstrip("/")
                instances.append(
                    ZipCompilerInstance(
                        name=name,
                        zip_path=zip_path,
                        valid=True,
                        language=lang,
                        object_code=obj,
                        config_path_in_zip=config_path,
                        project_root_in_zip=root,
                    )
                )
        except zipfile.BadZipFile:
            instances.append(ZipCompilerInstance(name=name, zip_path=zip_path, valid=False, reason="zip 文件损坏"))
        except Exception as e:
            instances.append(ZipCompilerInstance(name=name, zip_path=zip_path, valid=False, reason=str(e)))

    return instances


def extract_zip_instance(instance: ZipCompilerInstance, dest_root: Path) -> Path:
    """解包 zip 编译器实例到 dest_root，并返回解包后的项目根目录路径。"""
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    safe = _safe_name(instance.name)
    fingerprint = _zip_fingerprint(instance.zip_path)
    dest_dir = dest_root / f"{safe}_{fingerprint}"
    meta_path = dest_dir / _ZIP_META_FILE

    if dest_dir.exists() and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("fingerprint") == fingerprint and meta.get("zip_path") == str(instance.zip_path.resolve()):
                return _resolve_project_root(dest_dir, instance.project_root_in_zip)
        except Exception:
            pass

    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(instance.zip_path, "r") as zf:
        _safe_extract_all(zf, dest_dir)

    meta_path.write_text(
        json.dumps(
            {
                "zip_path": str(instance.zip_path.resolve()),
                "fingerprint": fingerprint,
                "project_root_in_zip": instance.project_root_in_zip,
                "config_path_in_zip": instance.config_path_in_zip,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return _resolve_project_root(dest_dir, instance.project_root_in_zip)


def _resolve_project_root(dest_dir: Path, project_root_in_zip: str) -> Path:
    root = (project_root_in_zip or "").strip().replace("\\", "/").strip("/")
    if not root:
        return dest_dir
    return (dest_dir / root).resolve()


def _safe_extract_all(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """安全解包：防止 zip-slip 写出到目标目录外。"""
    dest_dir = dest_dir.resolve()
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if _should_ignore_zip_entry(name):
            continue

        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"非法 zip 路径: {info.filename}")

        target = (dest_dir / rel).resolve()
        if dest_dir not in target.parents and target != dest_dir:
            raise ValueError(f"非法 zip 路径: {info.filename}")

        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info, "r") as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
