package org.sih.idr

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import android.os.SystemClock
import androidx.core.content.ContextCompat

data class PhoneSensorSample(
    val timestampNanos: Long,
    val accelerationX: Float,
    val accelerationY: Float,
    val accelerationZ: Float,
    val yawRateX: Float,
    val yawRateY: Float,
    val yawRateZ: Float,
    val magneticFieldX: Float,
    val magneticFieldY: Float,
    val magneticFieldZ: Float,
    val location: Location?,
    val stepCount: Long = 0L,
    val azimuthDeg: Double = -1.0,
)

interface SensorCaptureListener {
    fun onSample(sample: PhoneSensorSample)
    fun onHealthChanged(message: String)
}

class SensorCaptureController(
    context: Context,
    private val listener: SensorCaptureListener,
) : SensorEventListener {
    private val appContext = context.applicationContext
    private val sensorManager =
        appContext.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val locationManager =
        appContext.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private val accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
    private val magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
    private val stepDetector = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR)

    private var latestAcceleration = FloatArray(3)
    private var latestGyroscope = FloatArray(3)
    private var latestMagneticField = FloatArray(3)
    private val rotationMatrix = FloatArray(9)
    private val inclinationMatrix = FloatArray(9)
    private val orientationAngles = FloatArray(3)
    private var currentAzimuthDeg = -1.0
    private var latestLocation: Location? = null
    private var latestLocationReceivedNanos = 0L
    private var lastEmittedLocationNanos = 0L
    private var running = false
    private var mockOutageActive = false
    private var totalSteps = 0L
    private var lastStepMillis = 0L

    fun setManualOrigin(latitude: Double, longitude: Double) {
        val mock = Location("manual_venue_origin").apply {
            this.latitude = latitude
            this.longitude = longitude
            this.accuracy = 2.0f
            this.time = System.currentTimeMillis()
        }
        latestLocation = mock
        latestLocationReceivedNanos = SystemClock.elapsedRealtimeNanos()
        listener.onHealthChanged("Indoor venue origin anchored ($latitude, $longitude)")
    }

    fun toggleMockOutage(active: Boolean) {
        mockOutageActive = active
        if (active) {
            listener.onHealthChanged("GNSS signal cut active (Simulating tunnel outage)")
        } else {
            listener.onHealthChanged("GNSS signal restored")
        }
    }

    private val locationListener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            latestLocation = location
            latestLocationReceivedNanos = SystemClock.elapsedRealtimeNanos()
        }

        override fun onProviderEnabled(provider: String) {
            listener.onHealthChanged("GNSS provider enabled: $provider")
        }

        override fun onProviderDisabled(provider: String) {
            listener.onHealthChanged("GNSS provider disabled: $provider")
        }

        @Deprecated("Required for API compatibility")
        override fun onStatusChanged(provider: String, status: Int, extras: Bundle) {
            listener.onHealthChanged("GNSS provider status changed: $provider")
        }
    }

    fun start(): Boolean {
        if (running) return true
        if (!hasLocationPermission()) {
            listener.onHealthChanged("Location permission is required")
            return false
        }
        if (accelerometer == null || gyroscope == null) {
            listener.onHealthChanged("Required accelerometer or gyroscope is unavailable")
            return false
        }

        sensorManager.registerListener(
            this,
            accelerometer,
            SensorManager.SENSOR_DELAY_GAME,
        )
        sensorManager.registerListener(
            this,
            gyroscope,
            SensorManager.SENSOR_DELAY_GAME,
        )
        magnetometer?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }
        stepDetector?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_FASTEST)
        }

        // Immediately seed last known location so map doesn't start blank
        try {
            val lastGps = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            val lastNet = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            val best = when {
                lastGps != null && lastNet != null -> if (lastGps.time >= lastNet.time) lastGps else lastNet
                lastGps != null -> lastGps
                else -> lastNet
            }
            if (best != null) {
                latestLocation = best
                latestLocationReceivedNanos = SystemClock.elapsedRealtimeNanos()
            }
        } catch (_: SecurityException) {
        }

        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    LOCATION_INTERVAL_MS,
                    LOCATION_DISTANCE_M,
                    locationListener,
                    Looper.getMainLooper(),
                )
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    LOCATION_INTERVAL_MS,
                    LOCATION_DISTANCE_M,
                    locationListener,
                    Looper.getMainLooper(),
                )
            }
        } catch (securityException: SecurityException) {
            sensorManager.unregisterListener(this)
            listener.onHealthChanged("GNSS permission was revoked")
            return false
        }
        running = true
        listener.onHealthChanged("Sensors active; waiting for GNSS fix")
        return true
    }

    fun stop() {
        if (!running) return
        sensorManager.unregisterListener(this)
        if (hasLocationPermission()) {
            locationManager.removeUpdates(locationListener)
        }
        running = false
        listener.onHealthChanged("Sensors stopped")
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (!running) return
        when (event.sensor.type) {
            Sensor.TYPE_STEP_DETECTOR -> {
                totalSteps += 1
            }
            Sensor.TYPE_ACCELEROMETER -> {
                latestAcceleration = event.values.copyOf()
                val mag = kotlin.math.sqrt(
                    event.values[0] * event.values[0] +
                    event.values[1] * event.values[1] +
                    event.values[2] * event.values[2]
                )
                // Fallback step detector if physical step detector sensor is missing on device
                if (stepDetector == null && mag > 12.2f && (SystemClock.elapsedRealtime() - lastStepMillis > 340L)) {
                    lastStepMillis = SystemClock.elapsedRealtime()
                    totalSteps += 1
                }
                updateCompassOrientation()
            }
            Sensor.TYPE_GYROSCOPE -> latestGyroscope = event.values.copyOf()
            Sensor.TYPE_MAGNETIC_FIELD -> {
                latestMagneticField = event.values.copyOf()
                updateCompassOrientation()
            }
            else -> return
        }
        listener.onSample(
            PhoneSensorSample(
                timestampNanos = event.timestamp,
                accelerationX = latestAcceleration[0],
                accelerationY = latestAcceleration[1],
                accelerationZ = latestAcceleration[2],
                yawRateX = latestGyroscope[0],
                yawRateY = latestGyroscope[1],
                yawRateZ = latestGyroscope[2],
                magneticFieldX = latestMagneticField[0],
                magneticFieldY = latestMagneticField[1],
                magneticFieldZ = latestMagneticField[2],
                location = latestLocation
                    ?.takeIf {
                        !mockOutageActive &&
                            latestLocationReceivedNanos > lastEmittedLocationNanos &&
                            SystemClock.elapsedRealtimeNanos() - latestLocationReceivedNanos <= LOCATION_FRESHNESS_NS
                    }
                    ?.also {
                        lastEmittedLocationNanos = latestLocationReceivedNanos
                    }
                    ?.let(::Location),
                stepCount = totalSteps,
                azimuthDeg = currentAzimuthDeg,
            ),
        )
    }

    private fun updateCompassOrientation() {
        if (SensorManager.getRotationMatrix(rotationMatrix, inclinationMatrix, latestAcceleration, latestMagneticField)) {
            SensorManager.getOrientation(rotationMatrix, orientationAngles)
            var azimuth = Math.toDegrees(orientationAngles[0].toDouble())
            if (azimuth < 0.0) azimuth += 360.0
            currentAzimuthDeg = azimuth
        }
    }

    override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) {
        listener.onHealthChanged("${sensor.name} accuracy changed: $accuracy")
    }

    private fun hasLocationPermission(): Boolean =
        ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(
                appContext,
                Manifest.permission.ACCESS_COARSE_LOCATION,
            ) == PackageManager.PERMISSION_GRANTED

    companion object {
        private const val LOCATION_INTERVAL_MS = 1000L
        private const val LOCATION_DISTANCE_M = 0f
        private const val LOCATION_FRESHNESS_NS = 1_500_000_000L
    }
}
