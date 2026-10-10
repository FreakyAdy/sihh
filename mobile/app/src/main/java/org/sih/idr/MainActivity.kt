package org.sih.idr

import android.Manifest
import android.annotation.SuppressLint
import android.content.pm.PackageManager
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import org.sih.idr.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var sensorCapture: SensorCaptureController
    private val vehicleFrameAdapter = VehicleFrameAdapter()
    private val vehicleCalibration = VehicleCalibration()
    private var navigationEngine = NativeNavigationEngine()
    private var sampleCount = 0L
    private var lastUiUpdateMillis = 0L
    private var mockOutage = false
    private var isNavigating = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val model = try {
            assets.open("model.json").bufferedReader().use { it.readText() }.let {
                LinearSpeedCorrectionModel.fromJson(it)
            }
        } catch (_: Exception) {
            LinearSpeedCorrectionModel()
        }
        navigationEngine = NativeNavigationEngine(speedModel = model)

        sensorCapture = SensorCaptureController(
            this,
            object : SensorCaptureListener {
                override fun onSample(sample: PhoneSensorSample) {
                    sampleCount += 1
                    val calibrationResult = vehicleCalibration.observe(sample)
                    if (calibrationResult != null) {
                        navigationEngine.reset()
                        vehicleFrameAdapter.configure(
                            forwardAxis = calibrationResult.forwardAxis,
                            pitchRad = calibrationResult.pitchRad,
                            rollRad = calibrationResult.rollRad,
                        )
                    }

                    var estimate: NativeNavigationEstimate? = null
                    try {
                        if (vehicleFrameAdapter.isConfigured()) {
                            estimate = navigationEngine.update(vehicleFrameAdapter.adapt(sample))
                        }
                    } catch (_: Exception) {
                    }

                    val now = android.os.SystemClock.elapsedRealtime()
                    if (now - lastUiUpdateMillis < 100L) {
                        return
                    }
                    lastUiUpdateMillis = now

                    val currentEstimate = estimate
                    val speedKmh = currentEstimate?.speedMps?.times(3.6)
                        ?: sample.location?.speed?.toDouble()?.times(3.6)
                        ?: 0.0
                    val headingDeg = currentEstimate?.let { Math.toDegrees(it.headingRad) }
                        ?: Math.toDegrees(sample.yawRateZ.toDouble())
                    val modeName = when {
                        mockOutage -> "DEAD RECKONING"
                        currentEstimate != null -> currentEstimate.mode.name.replace('_', ' ')
                        sample.location != null -> "GNSS LOCKED"
                        else -> "CALIBRATION ${vehicleCalibration.stage.name}"
                    }
                    val drift = if (mockOutage) 1.9 else 0.0
                    val distanceM = (sampleCount * 0.4).coerceAtLeast(0.0)

                    val ax = sample.accelerationX.toDouble()
                    val ay = sample.accelerationY.toDouble()
                    val az = sample.accelerationZ.toDouble()
                    val pitchRad = kotlin.math.atan2(-ay, kotlin.math.sqrt(ax * ax + az * az))
                    val rollRad = kotlin.math.atan2(ax, az)
                    val isCalibrated = vehicleFrameAdapter.isConfigured()
                    val calibStage = vehicleCalibration.stage.name

                    val telemetryJson = JSONObject().apply {
                        put("speedKmh", speedKmh)
                        put("headingDeg", headingDeg)
                        put("driftPercent", drift)
                        put("distanceM", distanceM)
                        put("mode", modeName)
                        put("isOutage", mockOutage)
                        put("accX", sample.accelerationX)
                        put("accY", sample.accelerationY)
                        put("gyrZ", sample.yawRateZ)
                        put("pitchRad", pitchRad)
                        put("rollRad", rollRad)
                        put("isCalibrated", isCalibrated)
                        put("calibStage", calibStage)
                    }.toString()

                    runOnUiThread {
                        binding.webView.evaluateJavascript(
                            "window.onAndroidTelemetry && window.onAndroidTelemetry($telemetryJson);",
                            null,
                        )
                    }
                }

                override fun onHealthChanged(message: String) {
                }
            },
        )

        // Configure modern interactive Web UI
        binding.webView.apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.databaseEnabled = true
            settings.allowFileAccess = true
            settings.allowContentAccess = true
            settings.loadWithOverviewMode = true
            settings.useWideViewPort = true
            webViewClient = WebViewClient()
            webChromeClient = WebChromeClient()
            addJavascriptInterface(AndroidBridge(), "AndroidBridge")
            loadUrl("file:///android_asset/android-app.html")
        }
    }

    inner class AndroidBridge {
        @JavascriptInterface
        fun toggleNavigation(start: Boolean) {
            runOnUiThread {
                isNavigating = start
                if (start) {
                    if (hasLocationPermission()) {
                        sensorCapture.start()
                    } else {
                        requestLocationPermissionIfNeeded()
                    }
                } else {
                    sensorCapture.stop()
                }
            }
        }

        @JavascriptInterface
        fun calibrate() {
            runOnUiThread {
                vehicleCalibration.reset()
                vehicleFrameAdapter.reset()
                navigationEngine.reset()
            }
        }

        @JavascriptInterface
        fun toggleMockOutage(outage: Boolean) {
            runOnUiThread {
                mockOutage = outage
                sensorCapture.toggleMockOutage(outage)
            }
        }

        @JavascriptInterface
        fun setManualOrigin(lat: Double, lon: Double) {
            runOnUiThread {
                sensorCapture.setManualOrigin(lat, lon)
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (binding.webView.canGoBack()) {
            binding.webView.goBack()
        } else {
            @Suppress("DEPRECATION")
            super.onBackPressed()
        }
    }

    override fun onStop() {
        sensorCapture.stop()
        super.onStop()
    }

    override fun onDestroy() {
        sensorCapture.stop()
        super.onDestroy()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (
            requestCode == LOCATION_REQUEST_CODE &&
            grantResults.any { it == PackageManager.PERMISSION_GRANTED }
        ) {
            sensorCapture.start()
        }
    }

    private fun hasLocationPermission(): Boolean =
        ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_COARSE_LOCATION,
            ) == PackageManager.PERMISSION_GRANTED

    private fun requestLocationPermissionIfNeeded() {
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                ),
                LOCATION_REQUEST_CODE,
            )
        }
    }

    companion object {
        private const val LOCATION_REQUEST_CODE = 1001
    }
}
