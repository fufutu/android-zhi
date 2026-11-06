package com.androidzhi.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.androidzhi.app.MainActivity
import com.androidzhi.app.R
import com.androidzhi.app.audio.AudioPlayer
import com.androidzhi.app.audio.AudioRecorder
import com.androidzhi.app.data.model.*
import com.androidzhi.app.data.local.PreferencesDataStore
import com.androidzhi.app.protocol.Protocol
import com.androidzhi.app.protocol.WebSocketProtocol
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import javax.inject.Inject

/**
 * 语音服务
 */
@AndroidEntryPoint
class VoiceService : Service() {
    
    @Inject
    lateinit var preferencesDataStore: PreferencesDataStore
    
    @Inject
    lateinit var webSocketProtocol: WebSocketProtocol
    
    @Inject
    lateinit var audioRecorder: AudioRecorder
    
    @Inject
    lateinit var audioPlayer: AudioPlayer
    
    private val binder = LocalBinder()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    
    private val _deviceState: MutableStateFlow<DeviceState>
        get() = globalDeviceState
    val deviceState: StateFlow<DeviceState>
        get() = globalDeviceState
    
    private val _connectionState: MutableStateFlow<ConnectionState>
        get() = globalConnectionState
    val connectionState: StateFlow<ConnectionState>
        get() = globalConnectionState
    
    private var listeningMode = ListeningMode.MANUAL
    private var keepListening = false
    
    private var currentProtocol: Protocol? = null
    
    inner class LocalBinder : Binder() {
        fun getService(): VoiceService = this@VoiceService
    }
    
    override fun onCreate() {
        super.onCreate()
        instance = this
        createNotificationChannel()
        setupProtocol()
        observeAudioData()
    }
    
    override fun onBind(intent: Intent): IBinder = binder
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, createNotification())
        return START_STICKY
    }
    
    override fun onDestroy() {
        instance = null
        super.onDestroy()
        scope.cancel()
        stopAudio()
        disconnect()
    }
    
    private fun setupProtocol() {
        currentProtocol = webSocketProtocol
        
        scope.launch {
            currentProtocol?.connectionState?.collect { state ->
                _connectionState.value = state
            }
        }
        
        currentProtocol?.apply {
            onAudioChannelOpened {
                _deviceState.value = DeviceState.Listening
            }
            
            onAudioChannelClosed {
                _deviceState.value = DeviceState.Idle
            }
            
            onIncomingJson { json ->
                handleIncomingJson(json)
            }
            
            onIncomingAudio { data ->
                audioPlayer.playAudio(data)
            }
        }
    }
    
    private fun observeAudioData() {
        scope.launch {
            audioRecorder.audioDataFlow.collect { opusData ->
                currentProtocol?.sendAudio(opusData)
            }
        }
    }
    
    private fun handleIncomingJson(json: Map<String, Any>) {
        val type = json["type"] as? String
        
        when (type) {
            "tts" -> {
                val state = json["state"] as? String
                when (state) {
                    "start" -> {
                        _deviceState.value = DeviceState.Speaking
                        audioPlayer.startPlaying()
                    }
                    "stop" -> {
                        audioPlayer.stopPlaying()
                        if (keepListening) {
                            _deviceState.value = DeviceState.Listening
                        } else {
                            _deviceState.value = DeviceState.Idle
                        }
                    }
                }
            }
        }
    }
    
    fun connect() {
        scope.launch {
            _connectionState.value = ConnectionState.Connecting
            val success = currentProtocol?.connect() ?: false
            if (success) {
                currentProtocol?.openAudioChannel()
            }
        }
    }
    
    fun disconnect() {
        scope.launch {
            currentProtocol?.disconnect()
        }
    }
    
    fun startManualListening() {
        scope.launch {
            val connected = ensureConnected()
            if (!connected) return@launch
            
            keepListening = false
            
            if (_deviceState.value == DeviceState.Speaking) {
                currentProtocol?.sendAbortSpeaking()
                _deviceState.value = DeviceState.Idle
            }
            
            currentProtocol?.sendStartListening("manual")
            _deviceState.value = DeviceState.Listening
            audioRecorder.startRecording()
        }
    }
    
    fun stopManualListening() {
        audioRecorder.stopRecording()
        scope.launch {
            currentProtocol?.sendStopListening()
            _deviceState.value = DeviceState.Idle
        }
    }
    
    fun abortSpeaking() {
        scope.launch {
            currentProtocol?.sendAbortSpeaking()
            audioPlayer.stopPlaying()
            _deviceState.value = DeviceState.Idle
        }
    }
    
    private fun stopAudio() {
        audioRecorder.stopRecording()
        audioPlayer.stopPlaying()
    }
    
    private suspend fun ensureConnected(): Boolean {
        if (currentProtocol?.isAudioChannelOpened == true) {
            return true
        }
        return currentProtocol?.connect() ?: false
    }
    
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "小智AI语音服务",
                NotificationManager.IMPORTANCE_LOW
            )
            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }
    
    private fun createNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )
        
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("小智AI")
            .setContentText("语音服务运行中")
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }
    
    companion object {
        private const val NOTIFICATION_ID = 1
        private const val CHANNEL_ID = "voice_service_channel"
        
        @Volatile
        var instance: VoiceService? = null
            private set
        
        val globalDeviceState = MutableStateFlow<DeviceState>(DeviceState.Idle)
        val globalConnectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    }
}