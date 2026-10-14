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
    private val vehicleFrameAdapter = VehicleFrameAdapter().apply {
        configure(forwardAxis = DeviceForwardAxis.POSITIVE_Y)
    }
    private val vehicleCalibration = VehicleCalibration()
    private var navigationEngine = NativeNavigationEngine()
    private var sampleCount = 0L
    private var lastUiUpdateMillis = 0L
    private var mockOutage = false
    private var isNavigating = false
    private var continuousLat = 28.6139
    private var continuousLng = 77.2090
    private var hasLockedGps = false
    private var lastStepCount = 0L
    private var lastTimestampNanos = 0L
    private var currentHeadingDeg = 0.0
    // Distance & speed derived from steps
    private var distanceMeters = 0.0
    private var lastStepForSpeed = 0L
    private var lastSpeedTimestampNanos = 0L
    private var stepSpeedKmh = 0.0

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

                    // Continuous Position & Dead Reckoning Kinematics
                    if (sample.location != null && !mockOutage) {
                        continuousLat = sample.location.latitude
                        continuousLng = sample.location.longitude
                        hasLockedGps = true
                        // Keep step baseline current so first DR step is delta=0 not all steps since boot
                        lastStepCount = sample.stepCount
                        if (sample.location.hasBearing() && sample.location.speed > 0.5f) {
                            currentHeadingDeg = sample.location.bearing.toDouble()
                        } else if (sample.azimuthDeg >= 0.0) {
                            currentHeadingDeg = sample.azimuthDeg
                        }
                    } else {
                        // GPS Outage or Dead Reckoning active — PDR always runs
                        if (sample.azimuthDeg >= 0.0) {
                            currentHeadingDeg = sample.azimuthDeg
                        } else if (lastTimestampNanos > 0L) {
                            val dt = (sample.timestampNanos - lastTimestampNanos) / 1e9
                            if (dt in 0.001..0.5) {
                                currentHeadingDeg = (currentHeadingDeg - Math.toDegrees(sample.yawRateZ.toDouble()) * dt + 360.0) % 360.0
                            }
                        }

                        // Seed step baseline on first DR frame
                        if (lastStepCount == 0L || lastStepCount > sample.stepCount) {
                            lastStepCount = sample.stepCount
                        }
                        val deltaSteps = if (sample.stepCount >= lastStepCount) {
                            (sample.stepCount - lastStepCount).coerceIn(0L, 5L)
                        } else 0L

                        if (deltaSteps > 0L) {
                            lastStepCount = sample.stepCount
                            val strideM = deltaSteps * 0.75
                            distanceMeters += strideM
                            // Update step-cadence speed
                            val dtSec = if (lastSpeedTimestampNanos > 0L)
                                (sample.timestampNanos - lastSpeedTimestampNanos) / 1e9 else 0.0
                            if (dtSec >= 0.4) {
                                stepSpeedKmh = (strideM / dtSec) * 3.6
                                lastSpeedTimestampNanos = sample.timestampNanos
                                lastStepForSpeed = sample.stepCount
                            }
                            val rad = Math.toRadians(currentHeadingDeg)
                            val dLat = (strideM * kotlin.math.cos(rad)) / 111320.0
                            val dLng = (strideM * kotlin.math.sin(rad)) / (111320.0 * kotlin.math.cos(Math.toRadians(continuousLat)))
                            continuousLat += dLat
                            continuousLng += dLng
                        } else if (estimate != null && estimate.latitude != null && estimate.longitude != null) {
                            continuousLat = estimate.latitude
                            continuousLng = estimate.longitude
                        }
                    }
                    lastTimestampNanos = sample.timestampNanos

                    val now = android.os.SystemClock.elapsedRealtime()
                    if (now - lastUiUpdateMillis < 100L) {
                        return
                    }
                    lastUiUpdateMillis = now

                    val currentEstimate = estimate
                    val isActualOutage = mockOutage ||
                        (currentEstimate?.mode == NativeNavigationMode.DEAD_RECKONING) ||
                        (sample.location == null)  // PDR works with or without prior GPS fix
                    // Step-cadence speed: decay gradually when no new step arrives
                    if (sample.stepCount == lastStepForSpeed && lastSpeedTimestampNanos > 0L) {
                        val idleSec = (sample.timestampNanos - lastSpeedTimestampNanos) / 1e9
                        if (idleSec > 2.5) stepSpeedKmh = 0.0
                    }
                    val speedKmh = when {
                        isActualOutage && stepSpeedKmh > 0.1 -> stepSpeedKmh
                        isActualOutage -> 0.0
                        currentEstimate != null && currentEstimate.speedMps > 0.1 -> currentEstimate.speedMps * 3.6
                        sample.location != null && sample.location.hasSpeed() && sample.location.speed > 0.3f ->
                            sample.location.speed.toDouble() * 3.6
                        else -> stepSpeedKmh
                    }
                    val headingDeg = currentHeadingDeg
                    val modeName = when {
                        isActualOutage -> "DEAD RECKONING"
                        currentEstimate != null -> currentEstimate.mode.name.replace('_', ' ')
                        sample.location != null -> "GNSS LOCKED"
                        else -> "CALIBRATION ${vehicleCalibration.stage.name}"
                    }
                    val drift = if (mockOutage) 1.9 else 0.0
                    val distanceM = distanceMeters

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
                        put("driftPercent", if (isActualOutage) 1.9 else 0.0)
                        put("distanceM", distanceM)
                        put("stepCount", sample.stepCount)
                        put("mode", modeName)
                        put("isOutage", isActualOutage)
                        put("hasGps", sample.location != null && !mockOutage)
                        put("lat", continuousLat)
                        put("lng", continuousLng)

                        sample.location?.let { loc ->
                            put("rawLat", loc.latitude)
                            put("rawLng", loc.longitude)
                            put("accuracy", loc.accuracy.toDouble())
                        }

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

        if (hasLocationPermission()) {
            sensorCapture.start()
        } else {
            requestLocationPermissionIfNeeded()
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
                distanceMeters = 0.0
                stepSpeedKmh = 0.0
                lastStepForSpeed = 0L
                lastSpeedTimestampNanos = 0L
                lastStepCount = 0L
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
                continuousLat = lat
                continuousLng = lon
                hasLockedGps = true
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
