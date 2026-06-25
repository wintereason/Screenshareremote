package com.example.screenshareremote

import android.Manifest
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class ScanQrActivity : AppCompatActivity() {

    private lateinit var cameraExecutor: ExecutorService
    private var didReturnResult = false

    private val requestCameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startCamera()
        } else {
            showPermissionError()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_scan_qr)

        findViewById<Button>(R.id.btnClose).setOnClickListener {
            setResult(RESULT_CANCELED)
            finish()
        }

        cameraExecutor = Executors.newSingleThreadExecutor()

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            startCamera()
        } else {
            requestCameraPermission.launch(Manifest.permission.CAMERA)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
    }

    private fun showPermissionError() {
        Toast.makeText(
            this,
            "Camera permission is required to scan QR codes.",
            Toast.LENGTH_LONG
        ).show()
        setResult(RESULT_CANCELED)
        finish()
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener(
            {
                val cameraProvider = cameraProviderFuture.get()
                val previewView = findViewById<PreviewView>(R.id.previewView)

                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }

                val imageAnalysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also {
                        it.setAnalyzer(cameraExecutor, QrAnalyzer(::onQrScanned))
                    }

                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(
                        this,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageAnalysis
                    )
                } catch (exception: Exception) {
                    Toast.makeText(this, "Unable to start camera.", Toast.LENGTH_LONG).show()
                    setResult(RESULT_CANCELED)
                    finish()
                }
            },
            ContextCompat.getMainExecutor(this)
        )
    }

    private fun onQrScanned(value: String) {
        if (didReturnResult) return
        didReturnResult = true

        val data = Intent().putExtra(EXTRA_QR_VALUE, value)
        setResult(RESULT_OK, data)
        finish()
    }

    private class QrAnalyzer(
        private val onResult: (String) -> Unit
    ) : ImageAnalysis.Analyzer {

        private val scanner = BarcodeScanning.getClient()

        override fun analyze(imageProxy: ImageProxy) {
            val mediaImage = imageProxy.image
            if (mediaImage == null) {
                imageProxy.close()
                return
            }

            val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
            scanner.process(image)
                .addOnSuccessListener { barcodes ->
                    val value = barcodes.firstOrNull()?.rawValue
                    if (!value.isNullOrBlank()) {
                        onResult(value)
                    }
                }
                .addOnFailureListener { /* ignore errors */ }
                .addOnCompleteListener {
                    imageProxy.close()
                }
        }
    }

    companion object {
        const val EXTRA_QR_VALUE = "qr_value"
    }
}

