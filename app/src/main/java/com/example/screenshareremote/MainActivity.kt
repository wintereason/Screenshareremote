package com.example.screenshareremote

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private val scanQrLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val url = result.data?.getStringExtra(ScanQrActivity.EXTRA_QR_VALUE)?.trim()
            if (!url.isNullOrBlank()) {
                val normalized = normalizeServerUrl(url)
                saveServerUrl(normalized)
                findViewById<WebView>(R.id.webView).loadUrl(normalized)
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        enterImmersiveMode()

        val webView = findViewById<WebView>(R.id.webView)
        val scanButton = findViewById<Button>(R.id.btnScanQr)

        webView.webViewClient = WebViewClient()
        with(webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            useWideViewPort = true
            loadWithOverviewMode = true
        }

        scanButton.setOnClickListener {
            scanQrLauncher.launch(Intent(this, ScanQrActivity::class.java))
        }

        webView.loadUrl(loadServerUrl())
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            enterImmersiveMode()
        }
    }

    override fun onBackPressed() {
        val webView = findViewById<WebView>(R.id.webView)
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    private fun enterImmersiveMode() {
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
    }

    private fun loadServerUrl(): String {
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val saved = prefs.getString(PREF_SERVER_URL, null)?.trim()
        return if (!saved.isNullOrBlank()) saved else DEFAULT_SERVER_URL
    }

    private fun saveServerUrl(url: String) {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putString(PREF_SERVER_URL, url)
            .apply()
    }

    private fun normalizeServerUrl(value: String): String {
        val trimmed = value.trim()
        val withScheme = if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            trimmed
        } else {
            "http://$trimmed"
        }
        return if (withScheme.endsWith("/")) withScheme else "$withScheme/"
    }

    companion object {
        private const val PREFS_NAME = "ssr_prefs"
        private const val PREF_SERVER_URL = "server_url"
        private const val DEFAULT_SERVER_URL = "http://192.168.1.3:8080/"
    }
}