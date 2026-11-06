#!/usr/bin/env python3
"""
patch_android_zhi_final.py
==========================
一次性补齐 android-zhi 编译所需的全部修复。

修复内容：
  1. AndroidManifest.xml
       android:icon = "@drawable/ic_launcher_foreground"
       删除 android:roundIcon 行
  2. 删除 app/src/main/res/mipmap-anydpi-v26/（如存在）
  3. VoiceService.kt
       - 添加 companion 静态 instance + globalDeviceState / globalConnectionState
       - onCreate 设置 instance = this，onDestroy 清空
       - _deviceState / _connectionState 改为委托到全局 Flow（getter）
  4. MainViewModel.kt
       - 改为 @Inject constructor() 无参
       - deviceState / connectionState 直接引用 VoiceService.global*
       - init 中等待 instance 就绪后 connect
       - startListening / stopListening 通过 instance 调用
  5. Theme.kt
       - 补 import androidx.compose.ui.graphics.Color

用法：
  cd /path/to/android-zhi
  python3 patch_android_zhi_final.py
"""

import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path.cwd()


# ---------- 1. AndroidManifest.xml ----------
def patch_manifest() -> None:
    print("[1/5] 修复 AndroidManifest.xml 图标引用")
    path = REPO_ROOT / "app" / "src" / "main" / "AndroidManifest.xml"
    if not path.exists():
        print("  [!!] 找不到 AndroidManifest.xml，跳过")
        return

    content = path.read_text(encoding="utf-8")
    original = content

    content = content.replace(
        'android:icon="@mipmap/ic_launcher"',
        'android:icon="@drawable/ic_launcher_foreground"',
    )
    content = re.sub(
        r'\n\s*android:roundIcon="@mipmap/ic_launcher_round"',
        '',
        content,
    )

    if content != original:
        path.write_text(content, encoding="utf-8")
        print("  [OK] 图标改用 drawable/ic_launcher_foreground，删除 roundIcon")
    else:
        print("  [--] 图标引用已是目标状态，跳过")


# ---------- 2. 删除 mipmap-anydpi-v26 ----------
def delete_mipmap_anydpi() -> None:
    print("[2/5] 清理 mipmap-anydpi-v26")
    target = REPO_ROOT / "app" / "src" / "main" / "res" / "mipmap-anydpi-v26"
    if not target.exists():
        print("  [--] 目录不存在，跳过")
        return
    shutil.rmtree(target)
    print(f"  [OK] 已删除 {target.relative_to(REPO_ROOT)}")


# ---------- 3. VoiceService.kt ----------
VOICE_ORIG_STATES = """\
    private val _deviceState = MutableStateFlow<DeviceState>(DeviceState.Idle)
    val deviceState: StateFlow<DeviceState> = _deviceState.asStateFlow()
    
    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()
"""

VOICE_NEW_STATES = """\
    private val _deviceState: MutableStateFlow<DeviceState>
        get() = globalDeviceState
    val deviceState: StateFlow<DeviceState>
        get() = globalDeviceState
    
    private val _connectionState: MutableStateFlow<ConnectionState>
        get() = globalConnectionState
    val connectionState: StateFlow<ConnectionState>
        get() = globalConnectionState
"""

VOICE_ORIG_COMPANION = """\
    companion object {
        private const val NOTIFICATION_ID = 1
        private const val CHANNEL_ID = "voice_service_channel"
    }
"""

VOICE_NEW_COMPANION = """\
    companion object {
        private const val NOTIFICATION_ID = 1
        private const val CHANNEL_ID = "voice_service_channel"
        
        @Volatile
        var instance: VoiceService? = null
            private set
        
        val globalDeviceState = MutableStateFlow<DeviceState>(DeviceState.Idle)
        val globalConnectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    }
"""


def patch_voice_service() -> None:
    print("[3/5] 改造 VoiceService.kt")
    path = REPO_ROOT / "app" / "src" / "main" / "java" / "com" / "androidzhi" / "app" / "service" / "VoiceService.kt"
    if not path.exists():
        print("  [!!] 找不到 VoiceService.kt，跳过")
        return

    content = path.read_text(encoding="utf-8")
    original = content

    # 3a. state 委托到全局 Flow
    if VOICE_ORIG_STATES in content:
        content = content.replace(VOICE_ORIG_STATES, VOICE_NEW_STATES)
        print("  [OK] _deviceState/_connectionState 委托到全局 Flow")
    elif "get() = globalDeviceState" in content:
        print("  [--] state 委托已生效，跳过")
    else:
        print("  [!!] 未匹配到 state 定义，请手动检查")

    # 3b. onCreate 里加 instance = this
    onCreate_orig = "override fun onCreate() {\n        super.onCreate()\n        createNotificationChannel()"
    onCreate_new = "override fun onCreate() {\n        super.onCreate()\n        instance = this\n        createNotificationChannel()"
    if "instance = this" in content:
        print("  [--] onCreate 已有 instance = this，跳过")
    elif onCreate_orig in content:
        content = content.replace(onCreate_orig, onCreate_new)
        print("  [OK] onCreate 设置 instance = this")
    else:
        print("  [!!] 未匹配 onCreate 模式，请手动检查")

    # 3c. onDestroy 清空 instance
    onDestroy_orig = "override fun onDestroy() {\n        super.onDestroy()"
    onDestroy_new = "override fun onDestroy() {\n        instance = null\n        super.onDestroy()"
    if "instance = null" in content:
        print("  [--] onDestroy 已有 instance = null，跳过")
    elif onDestroy_orig in content:
        content = content.replace(onDestroy_orig, onDestroy_new)
        print("  [OK] onDestroy 清空 instance")
    else:
        print("  [!!] 未匹配 onDestroy 模式，请手动检查")

    # 3d. companion object 增加全局字段
    if "globalDeviceState" in content and "var instance: VoiceService" in content:
        print("  [--] companion 已包含全局字段，跳过")
    elif VOICE_ORIG_COMPANION in content:
        content = content.replace(VOICE_ORIG_COMPANION, VOICE_NEW_COMPANION)
        print("  [OK] companion object 增加 instance 和全局 Flow")
    else:
        print("  [!!] 未匹配 companion object，请手动检查")

    if content != original:
        path.write_text(content, encoding="utf-8")
        print("  已写入 VoiceService.kt")


# ---------- 4. MainViewModel.kt ----------
MAIN_VM_CONTENT = """\
package com.androidzhi.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.androidzhi.app.data.model.ConnectionState
import com.androidzhi.app.data.model.DeviceState
import com.androidzhi.app.service.VoiceService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * 主屏幕 ViewModel
 *
 * 注意：VoiceService 是 Android Service，Hilt 无法直接注入它的实例。
 * 这里改为通过 VoiceService.instance（静态引用）访问。
 * UI 状态通过 VoiceService.globalDeviceState / globalConnectionState 订阅，
 * 从而不依赖 ViewModel 创建时 Service 是否已经绑定完成。
 */
@HiltViewModel
class MainViewModel @Inject constructor() : ViewModel() {
    
    val deviceState: StateFlow<DeviceState> = VoiceService.globalDeviceState
    val connectionState: StateFlow<ConnectionState> = VoiceService.globalConnectionState
    
    init {
        viewModelScope.launch {
            var attempts = 0
            while (VoiceService.instance == null && attempts < 100) {
                delay(100)
                attempts++
            }
            VoiceService.instance?.connect()
        }
    }
    
    fun startListening() {
        VoiceService.instance?.startManualListening()
    }
    
    fun stopListening() {
        VoiceService.instance?.stopManualListening()
    }
}
"""


def rewrite_main_viewmodel() -> None:
    print("[4/5] 重写 MainViewModel.kt")
    path = REPO_ROOT / "app" / "src" / "main" / "java" / "com" / "androidzhi" / "app" / "ui" / "viewmodel" / "MainViewModel.kt"
    if not path.exists():
        print("  [!!] 找不到 MainViewModel.kt，跳过")
        return

    existing = path.read_text(encoding="utf-8")
    if "VoiceService.globalDeviceState" in existing and "@Inject constructor()" in existing:
        print("  [--] 已是新版，跳过")
        return

    path.write_text(MAIN_VM_CONTENT, encoding="utf-8")
    print("  [OK] 已重写（无参构造 + 静态访问 + 全局状态订阅）")


# ---------- 5. Theme.kt ----------
def patch_theme() -> None:
    print("[5/5] 修复 Theme.kt 缺失的 Color import")
    path = REPO_ROOT / "app" / "src" / "main" / "java" / "com" / "androidzhi" / "app" / "ui" / "theme" / "Theme.kt"
    if not path.exists():
        print("  [!!] 找不到 Theme.kt，跳过")
        return

    content = path.read_text(encoding="utf-8")
    original = content

    if "import androidx.compose.ui.graphics.Color" in content:
        print("  [--] Color 已 import，跳过")
        return

    needle = "import androidx.compose.runtime.Composable"
    if needle in content:
        content = content.replace(
            needle,
            needle + "\nimport androidx.compose.ui.graphics.Color",
            1,
        )
        path.write_text(content, encoding="utf-8")
        print("  [OK] 已补 import androidx.compose.ui.graphics.Color")
    else:
        print("  [!!] 未匹配 Composable import，请手动检查")
    _ = original


def main() -> None:
    print("=" * 64)
    print("  android-zhi 最终修补脚本 —— 打通编译")
    print("=" * 64)

    if not (REPO_ROOT / "settings.gradle.kts").exists():
        print("错误：请在仓库根目录（settings.gradle.kts 所在目录）运行")
        sys.exit(1)

    patch_manifest()
    delete_mipmap_anydpi()
    patch_voice_service()
    rewrite_main_viewmodel()
    patch_theme()

    print()
    print("=" * 64)
    print("完成。接下来：")
    print("  git add -A")
    print("  git commit -m 'fix: unblock build (icon, Hilt VM, Theme import)'")
    print("  git push")
    print("  到 GitHub Actions 等待 APK")
    print("=" * 64)


if __name__ == "__main__":
    main()
