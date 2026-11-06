#!/usr/bin/env python3
"""
patch_android_zhi.py
====================
为 android-zhi 项目打补丁，使其能编译并在 32 位 Android 8.1 小度智能屏上运行。

包含 4 项修改：

  1. app/build.gradle.kts
     - 删除过时的 composeOptions { kotlinCompilerExtensionVersion = ... }
     - 在 defaultConfig 里加入 ndk { abiFilters.add("armeabi-v7a") }

  2. .github/workflows/
     - 删除旧的 build-apk.yml
     - 写入 android.yml：用 gradle/actions/setup-gradle 安装 Gradle 8.11.1
       （匹配 AGP 8.8.0），不再依赖仓库里的 ./gradlew
     - 修复 android-actions/setup-android 因 Google 移除 'tools' 包导致的报错

  3. 如果本地存在 gradle 命令，则顺便生成 gradlew（可选，失败不影响 CI）

用法：
  cd /path/to/android-zhi
  python3 patch_android_zhi.py
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path.cwd()
GRADLE_VERSION = "8.11.1"

WORKFLOW = """\
name: Build Android APK

on:
  push:
    branches: [ "main", "master" ]
  pull_request:
    branches: [ "main", "master" ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
          cache: gradle

      - name: Setup Android SDK
        uses: android-actions/setup-android@v3
        with:
          # Google 已从 SDK 仓库移除 'tools' 包，显式指定 platform-tools 避免报错
          packages: 'platform-tools'

      - name: Setup Gradle
        uses: gradle/actions/setup-gradle@v4
        with:
          # AGP 8.8.0 要求 Gradle >= 8.10.2
          gradle-version: '8.11.1'

      - name: Build Debug APK
        run: gradle assembleDebug --stacktrace

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: android-zhi-debug-apk
          path: app/build/outputs/apk/debug/*.apk
          if-no-files-found: warn
"""


def find_gradle_file():
    for name in ("app/build.gradle.kts", "app/build.gradle"):
        p = REPO_ROOT / name
        if p.exists():
            return p
    return None


def patch_gradle(gradle_path: Path) -> None:
    print(f"[1/4] 修补 {gradle_path.relative_to(REPO_ROOT)}")
    content = gradle_path.read_text(encoding="utf-8")
    original = content

    # 1) 删除过时的 composeOptions
    pattern = re.compile(r'\n\s*composeOptions\s*\{[^}]*\}')
    if pattern.search(content):
        content = pattern.sub('', content)
        print("  [OK] 已删除过时的 composeOptions 块")
    elif 'composeOptions' in content:
        print("  [!!] 存在 composeOptions 但无法自动删除，请手动处理")
    else:
        print("  [--] 无 composeOptions，跳过")

    # 2) 添加 abiFilters
    marker = 'testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"'
    if 'abiFilters' in content:
        print("  [--] abiFilters 已存在，跳过")
    elif marker in content:
        replacement = (
            marker
            + '\n\n        ndk {\n'
              '            // 32-bit ARM（多数小度智能屏）\n'
              '            // 若 adb shell getprop ro.product.cpu.abi 返回 "x86"，\n'
              '            // 则改为 abiFilters.add("x86")\n'
              '            abiFilters.add("armeabi-v7a")\n'
              '        }'
        )
        content = content.replace(marker, replacement, 1)
        print('  [OK] 已添加 ndk { abiFilters.add("armeabi-v7a") }')
    else:
        print("  [!!] 找不到 testInstrumentationRunner 标记，请手动添加 abiFilters")

    if content != original:
        gradle_path.write_text(content, encoding="utf-8")
        print("  已写入更新")
    else:
        print("  文件无变化")


def fix_workflows() -> None:
    print("[2/4] 整理 .github/workflows/")
    wf_dir = REPO_ROOT / ".github" / "workflows"

    old = wf_dir / "build-apk.yml"
    if old.exists():
        old.unlink()
        print("  [OK] 已删除 build-apk.yml")
    else:
        print("  [--] 无 build-apk.yml，跳过")

    wf_dir.mkdir(parents=True, exist_ok=True)
    target = wf_dir / "android.yml"

    if target.exists():
        existing = target.read_text(encoding="utf-8").strip()
        if existing == WORKFLOW.strip():
            print("  [--] android.yml 已是最新，跳过")
            return
        print("  [OK] 覆盖已有 android.yml")
    else:
        print("  [OK] 创建 android.yml")

    target.write_text(WORKFLOW, encoding="utf-8")


def try_generate_wrapper() -> None:
    """可选：如果本地有 gradle，帮项目补一个 wrapper，方便本地 ./gradlew。"""
    print("[3/4] 检查 gradle wrapper（可选）")
    gw = REPO_ROOT / "gradlew"
    if gw.exists():
        print("  [--] gradlew 已存在，跳过生成")
        _make_executable(gw)
        return

    gradle_cmd = shutil.which("gradle")
    if not gradle_cmd:
        print("  [--] 仓库没有 gradlew，本地也没有 gradle 命令")
        print("      （不影响 CI，workflow 会用 setup-gradle 安装 Gradle）")
        return

    print(f"  [..] 本地发现 gradle：{gradle_cmd}，尝试生成 wrapper")
    try:
        subprocess.run(
            [gradle_cmd, "wrapper", "--gradle-version", GRADLE_VERSION],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        print("  [OK] 已生成 gradlew 和 gradle/wrapper/")
        _make_executable(gw)
    except subprocess.CalledProcessError as e:
        tail = (e.stderr or e.stdout or "").strip().splitlines()[-3:]
        print("  [!!] 生成 wrapper 失败（不影响 CI）：")
        for line in tail:
            print(f"       {line}")


def _make_executable(path: Path) -> None:
    if not path.exists():
        return
    if os.access(path, os.X_OK):
        print(f"  [--] {path.name} 已是可执行")
        return
    path.chmod(path.stat().st_mode | 0o111)
    print(f"  [OK] 已设置 {path.name} 可执行")


def check_project() -> None:
    print("[4/4] 检查项目结构")
    required = ["settings.gradle.kts", "app/build.gradle.kts"]
    missing = [f for f in required if not (REPO_ROOT / f).exists()]
    if missing:
        for f in missing:
            print(f"  [!!] 缺少 {f}")
        print("  请确认在仓库根目录运行本脚本")
        sys.exit(1)
    print("  [OK] 项目结构完整")


def main() -> None:
    print("=" * 62)
    print("  android-zhi 修补脚本（32 位 Android 8.1 小度智能屏）")
    print("=" * 62)

    if not find_gradle_file():
        print("错误：找不到 app/build.gradle(.kts)")
        print("请在仓库根目录（README.md 所在目录）运行本脚本")
        sys.exit(1)

    patch_gradle(find_gradle_file())
    fix_workflows()
    try_generate_wrapper()
    check_project()

    print()
    print("=" * 62)
    print("完成。接下来：")
    print("  ls .github/workflows/                 # 确认只剩 android.yml")
    print("  adb shell getprop ro.product.cpu.abi  # 确认 ABI 是 armeabi-v7a")
    print("  git add -A")
    print("  git commit -m 'fix: use setup-gradle, build for 32-bit Android 8.1'")
    print("  git push")
    print("  到 GitHub Actions 页面下载 APK")
    print("=" * 62)


if __name__ == "__main__":
    main()

