#!/usr/bin/env python3
"""
patch_android_zhi_aapt2_icon.py
===============================
修复 AAPT2 资源链接错误。

原因：
  项目 minSdk=24，但资源目录 mipmap-anydpi-v26 包含自适应图标。
  API 26 以下设备无法解析该资源，导致 AAPT2 在链接阶段失败。

操作：
  删除 app/src/main/res/mipmap-anydpi-v26/ 目录。
  （API 24-25 会回退到 mipmap-* 目录下的传统 PNG 图标）

用法：
  cd /path/to/android-zhi
  python3 patch_android_zhi_aapt2_icon.py
"""

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path.cwd()

def fix_adaptive_icon() -> None:
    print("[1/1] 清理冲突的自适应图标资源")

    target_dir = REPO_ROOT / "app" / "src" / "main" / "res" / "mipmap-anydpi-v26"

    if not target_dir.exists():
        print(f"  [--] 目录不存在，可能已修复: {target_dir.relative_to(REPO_ROOT)}")
        return

    try:
        shutil.rmtree(target_dir)
        print(f"  [OK] 已删除目录: {target_dir.relative_to(REPO_ROOT)}")
    except OSError as e:
        print(f"  [!!] 删除目录失败: {e}")
        print("       请手动删除该目录后重新构建。")
        sys.exit(1)

def main() -> None:
    print("=" * 58)
    print("  修复 AAPT2 自适应图标资源链接错误 (minSdk=24)")
    print("=" * 58)

    if not (REPO_ROOT / "settings.gradle.kts").exists():
        print("错误：请在仓库根目录（settings.gradle.kts 所在目录）运行")
        sys.exit(1)

    fix_adaptive_icon()

    print()
    print("=" * 58)
    print("完成。接下来：")
    print("  git add -A")
    print("  git commit -m 'fix: remove adaptive icon resources causing AAPT2 failure on minSdk 24'")
    print("  git push")
    print("  到 GitHub Actions 重新运行 workflow")
    print()
    print("注意：请确认 app/src/main/res/mipmap-*/ 目录下存在")
    print("       ic_launcher.png（或其他传统图标），否则 API 24/25 设备将无图标。")
    print("=" * 58)

if __name__ == "__main__":
    main()

