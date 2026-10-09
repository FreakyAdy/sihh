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
    private var latestAcceleration = FloatArray(3)
    private var latestGyroscope = FloatArray(3)
    private var latestMagneticField = FloatArray(3)
    private var latestLocation: Location? = null
    private var latestLocationReceivedNanos = 0L
    private var running = false

    private val locationListener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            latestLocation = location
            latestLocationReceivedNanos = SystemClock.elapsedRealtimeNanos()
        }

        override fun onProviderEnabled(provider: String) {
            listener.onHealthChanged("GNSS provider enabled")
        }

        override fun onProviderDisabled(provider: String) {
            listener.onHealthChanged("GNSS provider disabled")
        }

        @Deprecated("Required for API compatibility")
        override fun onStatusChanged(provider: String, status: Int, extras: Bundle) {
            listener.onHealthChanged("GNSS provider status changed")
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
        try {
            locationManager.requestLocationUpdates(
                LocationManager.GPS_PROVIDER,
                LOCATION_INTERVAL_MS,
                LOCATION_DISTANCE_M,
                locationListener,
                Looper.getMainLooper(),
            )
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
            Sensor.TYPE_ACCELEROMETER -> latestAcceleration = event.values.copyOf()
            Sensor.TYPE_GYROSCOPE -> latestGyroscope = event.values.copyOf()
            Sensor.TYPE_MAGNETIC_FIELD -> latestMagneticField = event.values.copyOf()
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
                        event.timestamp - latestLocationReceivedNanos <= LOCATION_FRESHNESS_NS
                    }
                    ?.let(::Location),
            ),
        )
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
