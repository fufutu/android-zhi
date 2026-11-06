#!/usr/bin/env python3
"""
patch_android_zhi_opus.py
=========================
移除项目中无效的 io.github.tans5:opus 依赖。

原因：
  io.github.tans5:opus:0.10.0 并未发布到 Google Maven 或 Maven Central。
  同时，项目中的 AudioPlayer/AudioRecorder 直接使用 Android 原生的
  AudioTrack/AudioRecord 处理 PCM 数据，并未实际调用 Opus API。

操作：
  1. 从 gradle/libs.versions.toml 中删除 opus 相关的 version 和 library 定义。
  2. 从 app/build.gradle.kts 中删除 implementation(libs.opus.android) 行。

用法：
  cd /path/to/android-zhi
  python3 patch_android_zhi_opus.py
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path.cwd()


def patch_version_catalog() -> None:
    print("[1/2] 清理 gradle/libs.versions.toml")
    toml_path = REPO_ROOT / "gradle" / "libs.versions.toml"
    if not toml_path.exists():
        print("  [!!] 找不到 gradle/libs.versions.toml，跳过")
        return

    content = toml_path.read_text(encoding="utf-8")
    original = content

    # 删除 [versions] 中的 opus 行
    content = re.sub(r'^opus\s*=.*\n', '', content, flags=re.MULTILINE)

    # 删除 [libraries] 中的 opus-android 行
    content = re.sub(r'^opus-android\s*=.*\n', '', content, flags=re.MULTILINE)

    if content != original:
        toml_path.write_text(content, encoding="utf-8")
        print("  [OK] 已从 libs.versions.toml 移除 opus 定义")
    else:
        print("  [--] libs.versions.toml 中无 opus 定义（或已清理）")


def patch_app_build_gradle() -> None:
    print("[2/2] 清理 app/build.gradle.kts")
    gradle_path = REPO_ROOT / "app" / "build.gradle.kts"
    if not gradle_path.exists():
        print("  [!!] 找不到 app/build.gradle.kts，跳过")
        return

    content = gradle_path.read_text(encoding="utf-8")
    original = content

    # 删除 implementation(libs.opus.android) 行，兼容可能的空白字符
    pattern = re.compile(r'^\s*implementation\(libs\.opus\.android\)\s*\n', re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub('', content)
        print("  [OK] 已移除 implementation(libs.opus.android)")
    else:
        print("  [--] app/build.gradle.kts 中未找到 opus 依赖（或已清理）")

    if content != original:
        gradle_path.write_text(content, encoding="utf-8")


def main() -> None:
    print("=" * 58)
    print("  移除无效的 io.github.tans5:opus 依赖")
    print("=" * 58)

    if not (REPO_ROOT / "settings.gradle.kts").exists():
        print("错误：请在仓库根目录（settings.gradle.kts 所在目录）运行")
        sys.exit(1)

    patch_version_catalog()
    patch_app_build_gradle()

    print()
    print("=" * 58)
    print("完成。接下来：")
    print("  git add gradle/libs.versions.toml app/build.gradle.kts")
    print("  git commit -m 'fix: remove unavailable io.github.tans5:opus dependency'")
    print("  git push")
    print("  到 GitHub Actions 重新运行 workflow")
    print("=" * 58)


if __name__ == "__main__":
    main()
