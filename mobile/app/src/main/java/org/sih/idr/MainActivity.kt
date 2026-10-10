package org.sih.idr

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.sih.idr.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var sensorCapture: SensorCaptureController
    private val vehicleFrameAdapter = VehicleFrameAdapter()
    private val vehicleCalibration = VehicleCalibration()
    private val navigationEngine = NativeNavigationEngine()
    private var sampleCount = 0L
    private var lastUiUpdateMillis = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

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
                    val now = android.os.SystemClock.elapsedRealtime()
                    if (now - lastUiUpdateMillis < 100L) {
                        return
                    }
                    lastUiUpdateMillis = now

                    var positionText: String
                    var modeText: String
                    var diagnostic = "Diagnostics: $sampleCount samples received (10 Hz display)"

                    try {
                        if (vehicleFrameAdapter.isConfigured()) {
                            val estimate = navigationEngine.update(vehicleFrameAdapter.adapt(sample))
                            positionText = estimate.latitude?.let { latitude ->
                                "Position: %.5f, %.5f".format(latitude, estimate.longitude)
                            } ?: "Position: waiting for GNSS origin"
                            modeText = "Mode: ${estimate.mode.name.replace('_', ' ')} (confidence %.2f)".format(estimate.confidence)
                        } else {
                            positionText = sample.location?.let {
                                "GNSS: %.5f, %.5f".format(it.latitude, it.longitude)
                            } ?: "GNSS: waiting for fix"
                            modeText = "Mode: Calibration ${vehicleCalibration.stage.name.lowercase()}"
                        }
                    } catch (error: IllegalArgumentException) {
                        positionText = "Position: error"
                        modeText = "Mode: Error"
                        diagnostic = "Diagnostics: rejected sensor sample (${error.message})"
                    } catch (error: IllegalStateException) {
                        positionText = "Position: unavailable"
                        modeText = "Mode: Error"
                        diagnostic = "Diagnostics: navigation unavailable (${error.message})"
                    }

                    runOnUiThread {
                        binding.position.text = positionText
                        binding.mode.text = modeText
                        binding.diagnostics.text = diagnostic
                    }
                }

                override fun onHealthChanged(message: String) {
                    runOnUiThread {
                        binding.diagnostics.text = "Diagnostics: $message"
                    }
                }
            },
        )
        binding.calibrate.setOnClickListener {
            vehicleCalibration.reset()
            vehicleFrameAdapter.reset()
            navigationEngine.reset()
            binding.mode.text = "Mode: Calibration stationary"
            binding.diagnostics.text = "Diagnostics: keep phone still, then drive straight"
        }
        binding.start.setOnClickListener {
            if (hasLocationPermission()) {
                sensorCapture.start()
            } else {
                requestLocationPermissionIfNeeded()
            }
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
        } else if (requestCode == LOCATION_REQUEST_CODE) {
            binding.diagnostics.text = "Diagnostics: location permission denied"
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
