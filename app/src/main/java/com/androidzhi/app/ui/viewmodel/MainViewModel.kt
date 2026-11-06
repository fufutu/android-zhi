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
