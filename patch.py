#!/usr/bin/env python3
"""
patch_android_zhi.py
====================
为 android-zhi 项目打补丁，使其能编译并在 32 位 Android 8.1 小度智能屏上运行。

包含 3 项修改：

  1. app/build.gradle.kts
     - 删除过时的 composeOptions { kotlinCompilerExtensionVersion = ... }
     - 在 defaultConfig 里加入 ndk { abiFilters.add("armeabi-v7a") }

  2. .github/workflows/
     - 删除旧的 build-apk.yml（里面用 setup-android 默认安装，会因 Google 移除
       'tools' 包而报错）
     - 创建 android.yml：显式指定 packages: 'platform-tools'，并用 ./gradlew
       避免 AGP 8.8 与全局 Gradle 版本冲突

  3. ./gradlew 加可执行权限

用法：
  cd /path/to/android-zhi
  python3 patch_android_zhi.py
"""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path.cwd()

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

      - name: Make gradlew executable
        run: chmod +x gradlew

      - name: Build Debug APK
        run: ./gradlew assembleDebug --stacktrace

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
    print(f"[1/3] 修补 {gradle_path.relative_to(REPO_ROOT)}")
    content = gradle_path.read_text(encoding="utf-8")
    original = content

    # 1. 删除过时的 composeOptions
    pattern = re.compile(r'\n\s*composeOptions\s*\{[^}]*\}')
    if pattern.search(content):
        content = pattern.sub('', content)
        print("  [OK] 已删除过时的 composeOptions 块")
    elif 'composeOptions' in content:
        print("  [!!] 存在 composeOptions 但无法自动删除，请手动处理")
    else:
        print("  [--] 无 composeOptions，跳过")

    # 2. 添加 abiFilters
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
    print("[2/3] 整理 .github/workflows/")
    wf_dir = REPO_ROOT / ".github" / "workflows"

    # 删除旧的 build-apk.yml
    old = wf_dir / "build-apk.yml"
    if old.exists():
        old.unlink()
        print("  [OK] 已删除 build-apk.yml")
    else:
        print("  [--] 无 build-apk.yml，跳过")

    # 创建/覆盖 android.yml
    wf_dir.mkdir(parents=True, exist_ok=True)
    target = wf_dir / "android.yml"

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        already_fixed = (
            "./gradlew assembleDebug" in existing
            and "packages: 'platform-tools'" in existing
            and "gradle-version" not in existing
        )
        if already_fixed:
            print("  [--] android.yml 已是最新修复版，跳过")
            return
        print("  [OK] 覆盖已有 android.yml")
    else:
        print("  [OK] 创建 android.yml")

    target.write_text(WORKFLOW, encoding="utf-8")


def make_gradlew_executable() -> None:
    print("[3/3] 设置 gradlew 可执行权限")
    gw = REPO_ROOT / "gradlew"
    if not gw.exists():
        print("  [!!] 找不到 ./gradlew，请确认在仓库根目录运行")
        return
    if os.access(gw, os.X_OK):
        print("  [--] 已是可执行")
        return
    gw.chmod(gw.stat().st_mode | 0o111)
    print("  [OK] 已设置")


def main() -> None:
    print("=" * 62)
    print("  android-zhi 修补脚本（32 位 Android 8.1 小度智能屏）")
    print("=" * 62)

    gradle_file = find_gradle_file()
    if not gradle_file:
        print("错误：找不到 app/build.gradle(.kts)")
        print("请在仓库根目录（README.md 所在目录）运行本脚本")
        sys.exit(1)

    patch_gradle(gradle_file)
    fix_workflows()
    make_gradlew_executable()

    print()
    print("=" * 62)
    print("完成。接下来：")
    print("  ls .github/workflows/                 # 确认只剩 android.yml")
    print("  adb shell getprop ro.product.cpu.abi  # 确认 ABI 是 armeabi-v7a")
    print("  git add -A")
    print("  git commit -m 'fix: build config for 32-bit Android 8.1'")
    print("  git push")
    print("  到 GitHub Actions 页面下载 APK")
    print("=" * 62)


if __name__ == "__main__":
    main()
