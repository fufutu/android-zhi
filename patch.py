#!/usr/bin/env python3
"""
patch_android_zhi.py
====================
修复 android-zhi 项目在 GitHub Actions 上构建失败的问题：

  1. settings.gradle.kts
     - 重写 dependencyResolutionManagement，确保 google() 和 mavenCentral()
       都在 repositories {} 块内，并加上阿里云镜像加速。
     - 解决 "Could not find androidx.databinding:databinding-compiler-common:8.8.0"
       的报错。

  2. .github/workflows/android.yml
     - 将 setup-gradle 的 gradle-version 从 8.2 改为 8.11.1
       （AGP 8.8.0 要求 Gradle >= 8.10.2）。

用法：
  cd /path/to/android-zhi
  python3 patch_android_zhi.py
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path.cwd()

# ---------- settings.gradle.kts 模板 ----------
SETTINGS_KTS = """\
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
        maven { url = uri("https://maven.aliyun.com/repository/gradle-plugin") }
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://maven.aliyun.com/repository/public") }
        maven { url = uri("https://maven.aliyun.com/repository/google") }
    }
}

rootProject.name = "android-zhi"
include(":app")
"""

# ---------- workflow 模板 ----------
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
          packages: 'platform-tools'

      - name: Setup Gradle
        uses: gradle/actions/setup-gradle@v4
        with:
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


def patch_settings() -> None:
    print("[1/2] 重写 settings.gradle.kts（修复仓库配置）")
    target = REPO_ROOT / "settings.gradle.kts"
    if not target.exists():
        print("  [!!] 找不到 settings.gradle.kts，请在仓库根目录运行")
        sys.exit(1)

    existing = target.read_text(encoding="utf-8").strip()
    if existing == SETTINGS_KTS.strip():
        print("  [--] settings.gradle.kts 已是最新修复版，跳过")
        return

    target.write_text(SETTINGS_KTS, encoding="utf-8")
    print("  [OK] 已写入修复后的 settings.gradle.kts")


def patch_workflow() -> None:
    print("[2/2] 更新 .github/workflows/android.yml（升级 Gradle 版本）")
    wf_dir = REPO_ROOT / ".github" / "workflows"
    wf = wf_dir / "android.yml"

    if not wf.exists():
        print("  [!!] android.yml 不存在，先运行上一个脚本创建它")
        return

    content = wf.read_text(encoding="utf-8")
    original = content

    # 将 gradle-version 替换为 8.11.1
    content = re.sub(
        r"gradle-version:\s*['\"]?[\d.]+['\"]?",
        "gradle-version: '8.11.1'",
        content,
    )

    if content != original:
        wf.write_text(content, encoding="utf-8")
        print("  [OK] 已将 Gradle 版本改为 8.11.1")
    else:
        if "8.11.1" in content:
            print("  [--] Gradle 版本已是 8.11.1，跳过")
        else:
            print("  [!!] 未找到 gradle-version 字段，请手动检查")


def main() -> None:
    print("=" * 62)
    print("  android-zhi 修补脚本 — 修复仓库配置与 Gradle 版本")
    print("=" * 62)

    patch_settings()
    patch_workflow()

    print()
    print("=" * 62)
    print("完成。接下来：")
    print("  git add settings.gradle.kts .github/workflows/android.yml")
    print("  git commit -m 'fix: correct repositories + bump Gradle to 8.11.1'")
    print("  git push")
    print("  到 GitHub Actions 页面重新运行 workflow")
    print("=" * 62)


if __name__ == "__main__":
    main()

