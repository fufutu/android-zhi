#!/usr/bin/env python3
"""
patch_android_zhi.py
====================
Patch script for the android-zhi project, aimed at building for a rooted
Xiaodu Smart Screen running Android 8.1 (32-bit).

It performs 3 things:

  1. In app/build.gradle.kts:
       * Removes the obsolete `composeOptions { kotlinCompilerExtensionVersion = ... }`
         block. The project already uses Kotlin 2.0.0 + org.jetbrains.kotlin.plugin.compose,
         which bundles the Compose compiler; the old explicit version can break the build.
       * Adds `ndk { abiFilters.add("armeabi-v7a") }` to defaultConfig so the APK only
         contains 32-bit ARM native libraries.

  2. Creates .github/workflows/build-apk.yml, a GitHub Actions workflow that builds
     a debug APK and uploads it as an artifact.

  3. Makes ./gradlew executable.

Usage
-----
  cd /path/to/android-zhi
  python3 patch_android_zhi.py

The script is idempotent: running it again is harmless.
"""

import os
import re
import sys
import shutil
from pathlib import Path

REPO_ROOT = Path.cwd()


def find_gradle_file():
    for name in ("app/build.gradle.kts", "app/build.gradle"):
        p = REPO_ROOT / name
        if p.exists():
            return p
    return None


def patch_gradle(gradle_path: Path) -> None:
    print(f"  File: {gradle_path}")
    original = gradle_path.read_text(encoding="utf-8")
    content = original
    changes = []

    # ---- 1. Remove obsolete composeOptions block ----
    compose_pattern = re.compile(r'\n\s*composeOptions\s*\{[^}]*\}')
    if compose_pattern.search(content):
        content = compose_pattern.sub('', content)
        changes.append(
            "  [OK] Removed obsolete composeOptions block "
            "(Kotlin 2.0 bundles the Compose compiler)"
        )
    elif 'composeOptions' in content:
        changes.append(
            "  [!!] composeOptions detected but could not be removed automatically; "
            "please delete it manually."
        )
    else:
        changes.append("  [--] composeOptions not present (nothing to do)")

    # ---- 2. Add abiFilters to defaultConfig ----
    marker = 'testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"'
    if 'abiFilters' in content:
        changes.append("  [--] abiFilters already present (skipped)")
    elif marker in content:
        replacement = (
            marker
            + '\n\n        ndk {\n'
              '            // 32-bit ARM (most Xiaodu Smart Screens)\n'
              '            // If `adb shell getprop ro.product.cpu.abi` returns "x86",\n'
              '            // change this to: abiFilters.add("x86")\n'
              '            abiFilters.add("armeabi-v7a")\n'
              '        }'
        )
        content = content.replace(marker, replacement, 1)
        changes.append(
            '  [OK] Added ndk { abiFilters.add("armeabi-v7a") } to defaultConfig'
        )
    else:
        changes.append(
            "  [!!] Could not find testInstrumentationRunner marker; "
            "add abiFilters manually."
        )

    # ---- Write file (with backup) ----
    if content != original:
        backup = gradle_path.with_suffix(gradle_path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(gradle_path, backup)
            print(f"  Backup: {backup.name}")
        gradle_path.write_text(content, encoding="utf-8")
        print("  Wrote updated build file.")
    else:
        print("  No changes written.")

    for line in changes:
        print(line)


WORKFLOW_YAML = """\
name: Build Android APK

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'

      - name: Set up Android SDK
        uses: android-actions/setup-android@v3

      - name: Make gradlew executable
        run: chmod +x gradlew

      - name: Build debug APK
        run: ./gradlew assembleDebug --stacktrace

      - name: Upload debug APK
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: android-zhi-debug-apk
          path: app/build/outputs/apk/debug/*.apk
          if-no-files-found: warn
"""


def create_workflow() -> None:
    wf_dir = REPO_ROOT / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf = wf_dir / "build-apk.yml"
    if wf.exists():
        print(f"  [--] {wf.relative_to(REPO_ROOT)} already exists (skipped)")
        return
    wf.write_text(WORKFLOW_YAML, encoding="utf-8")
    print(f"  [OK] Created {wf.relative_to(REPO_ROOT)}")


def make_gradlew_executable() -> None:
    gw = REPO_ROOT / "gradlew"
    if not gw.exists():
        print("  [!!] ./gradlew not found at repo root (is the wrapper committed?)")
        return
    if os.access(gw, os.X_OK):
        print("  [--] ./gradlew already executable")
        return
    mode = gw.stat().st_mode
    gw.chmod(mode | 0o111)
    print("  [OK] Made ./gradlew executable")


def abi_reminder() -> None:
    gradle_file = find_gradle_file()
    if not gradle_file:
        return
    txt = gradle_file.read_text(encoding="utf-8")
    if 'abiFilters.add("armeabi-v7a")' in txt:
        print()
        print("  Reminder: abiFilters is 'armeabi-v7a' (32-bit ARM).")
        print("  Verify on your rooted device with:")
        print("      adb shell getprop ro.product.cpu.abi")
        print("  If it prints 'x86', edit app/build.gradle.kts and use:")
        print('      abiFilters.add("x86")')


def main() -> None:
    print("=" * 68)
    print("  Android-Zhi patcher  —  for 32-bit Android 8.1 smart screen")
    print("=" * 68)

    gradle_file = find_gradle_file()
    if not gradle_file:
        print()
        print("ERROR: app/build.gradle(.kts) not found.")
        print("Run this script from the repository root (where README.md is).")
        sys.exit(1)

    print("\n[1/3] Patching Gradle build file")
    patch_gradle(gradle_file)

    print("\n[2/3] Creating GitHub Actions workflow")
    create_workflow()

    print("\n[3/3] Fixing gradlew permissions")
    make_gradlew_executable()

    abi_reminder()

    print()
    print("=" * 68)
    print("Done. Next steps:")
    print("  git add app/build.gradle.kts .github/workflows/build-apk.yml")
    print("  git commit -m 'chore: build config for 32-bit Android 8.1'")
    print("  git push")
    print("  Download the APK from the 'Actions' tab on GitHub.")
    print("=" * 68)


if __name__ == "__main__":
    main()
