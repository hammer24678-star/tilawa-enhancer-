package com.tilawa.tilawa_enhancer

import android.content.ContentValues
import android.media.MediaScannerConnection
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
    LocalEngineRunner(this, applicationContext).registerWith(flutterEngine) // S65
        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "com.tilawa.tilawa_enhancer/media"
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "scanFile" -> {
                    val path = call.argument<String>("path")
                    if (path != null) {
                        MediaScannerConnection.scanFile(
                            this, arrayOf(path), arrayOf("audio/mpeg")
                        ) { _, _ -> result.success(null) }
                    } else {
                        result.error("INVALID_PATH", "path is null", null)
                    }
                }
                "saveToDownloads" -> {
                    val sourcePath = call.argument<String>("path")
                    val fileName   = call.argument<String>("filename")
                    // S208: restores a fix (orig. S157) lost in S207 template resync —
                    // v11.0/الصفاء and WAV audio-editor exports are actually WAV, not MP3;
                    // tagging them "audio/mpeg" mislabels the MediaStore/share-intent MIME.
                    val mimeType = if (fileName?.endsWith(".wav") == true) "audio/wav" else "audio/mpeg"
                    if (sourcePath == null || fileName == null) {
                        result.error("INVALID_ARGS", "path or filename is null", null)
                        return@setMethodCallHandler
                    }
                    try {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                            val resolver = contentResolver
                            val values = ContentValues().apply {
                                put(MediaStore.Downloads.DISPLAY_NAME, fileName)
                                put(MediaStore.Downloads.MIME_TYPE, mimeType)  // S208
                                put(MediaStore.Downloads.IS_PENDING, 1)
                            }
                            val collection = MediaStore.Downloads.getContentUri(
                                MediaStore.VOLUME_EXTERNAL_PRIMARY
                            )
                            val itemUri = resolver.insert(collection, values)
                            if (itemUri == null) {
                                result.error("INSERT_FAILED", "MediaStore insert returned null", null)
                                return@setMethodCallHandler
                            }
                            // RC2 FIX: explicit null check prevents phantom 0-byte MediaStore entry
                            val outputStream = resolver.openOutputStream(itemUri)
                            if (outputStream == null) {
                                resolver.delete(itemUri, null, null)
                                result.error("STREAM_FAILED", "MediaStore openOutputStream returned null", null)
                                return@setMethodCallHandler
                            }
                            outputStream.use { out ->
                                java.io.File(sourcePath).inputStream().use { input -> input.copyTo(out) }
                            }
                            values.clear()
                            values.put(MediaStore.Downloads.IS_PENDING, 0)
                            resolver.update(itemUri, values, null, null)
                            result.success(itemUri.toString())
                        } else {
                            // RC1 FIX: background Thread prevents ANR on large files
                            Thread {
                                try {
                                    val downloadsDir = Environment.getExternalStoragePublicDirectory(
                                        Environment.DIRECTORY_DOWNLOADS
                                    )
                                    downloadsDir.mkdirs()
                                    val dest = java.io.File(downloadsDir, fileName)
                                    java.io.File(sourcePath).copyTo(dest, overwrite = true)
                                    MediaScannerConnection.scanFile(
                                        this@MainActivity,
                                        arrayOf(dest.absolutePath),
                                        arrayOf(mimeType)  // S208
                                    ) { _, _ -> result.success(dest.absolutePath) }
                                } catch (e: Exception) {
                                    android.os.Handler(android.os.Looper.getMainLooper()).post {
                                        result.error("SAVE_FAILED", e.message, null)
                                    }
                                }
                            }.start()
                        }
                    } catch (e: Exception) {
                        result.error("SAVE_FAILED", e.message, null)
                    }
                }
                "shareFile" -> {
                    val uriString = call.argument<String>("uri")
                    if (uriString != null) {
                        try {
                            val shareUri = android.net.Uri.parse(uriString)
                            // S208: same WAV-vs-MP3 fix as saveToDownloads above, for the share Intent
                            val shareMime = if (uriString.endsWith(".wav")) "audio/wav" else "audio/mpeg"
                            val intent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                                type = shareMime
                                putExtra(android.content.Intent.EXTRA_STREAM, shareUri)
                                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            }
                            startActivity(android.content.Intent.createChooser(intent, "Share"))
                            result.success(null)
                        } catch (e: Exception) {
                            result.error("SHARE_FAILED", e.message, null)
                        }
                    } else {
                        result.error("INVALID_ARGS", "uri is null", null)
                    }
                }
                else -> result.notImplemented()
            }
        }

        // S63: CPU wake lock — keeps polling alive with screen off
        var _wl: android.os.PowerManager.WakeLock? = null
        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "com.tilawa.tilawa_enhancer/wake"
        ).setMethodCallHandler { call, result ->
            val pm = getSystemService(POWER_SERVICE) as android.os.PowerManager
            when (call.method) {
                "acquire" -> {
                    _wl?.let { if (it.isHeld) it.release() }
                    _wl = pm.newWakeLock(
                        android.os.PowerManager.PARTIAL_WAKE_LOCK,
                        "tilawa:processing"
                    ).also { it.acquire(90 * 60 * 1000L) }  // S207: was 10min — too short for LocalEngineRunner's own 90-min
                    // engine timeout; the device could doze mid-run on long/degraded files
                    // S191: PARTIAL_WAKE_LOCK alone only keeps the CPU running —
                    // it does nothing for the display, so the screen could still
                    // time out/lock during processing. Force it to stay on too.
                    runOnUiThread { window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }
                    result.success(null)
                }
                "release" -> {
                    _wl?.let { if (it.isHeld) it.release() }
                    _wl = null
                    runOnUiThread { window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }  // S191
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }
}
