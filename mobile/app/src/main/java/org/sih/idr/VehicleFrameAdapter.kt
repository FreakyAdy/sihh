package org.sih.idr

import kotlin.math.sin

data class VehicleImuSample(
    val timestampSeconds: Double,
    val forwardAccelerationMps2: Double,
    val yawRateRps: Double,
    val location: android.location.Location?,
)

enum class DeviceForwardAxis {
    POSITIVE_X,
    NEGATIVE_X,
    POSITIVE_Y,
    NEGATIVE_Y,
    POSITIVE_Z,
    NEGATIVE_Z,
}

class VehicleFrameAdapter {
    private var isCalibrated = false
    private var deviceForwardAxis = DeviceForwardAxis.POSITIVE_Y
    private var pitchRad = 0.0
    private var rollRad = 0.0

    fun configure(
        forwardAxis: DeviceForwardAxis = DeviceForwardAxis.POSITIVE_Y,
        pitchRad: Double = 0.0,
        rollRad: Double = 0.0,
    ) {
        require(pitchRad.isFinite()) { "pitch must be finite" }
        require(rollRad.isFinite()) { "roll must be finite" }
        this.deviceForwardAxis = forwardAxis
        this.pitchRad = pitchRad
        this.rollRad = rollRad
        this.isCalibrated = true
    }

    // Overload for compatibility
    fun configure(
        vehicleHeadingRad: Double,
        forwardAxis: DeviceForwardAxis = DeviceForwardAxis.POSITIVE_Y,
    ) {
        configure(forwardAxis = forwardAxis, pitchRad = 0.0, rollRad = 0.0)
    }

    fun isConfigured(): Boolean = isCalibrated

    fun reset() {
        isCalibrated = false
        deviceForwardAxis = DeviceForwardAxis.POSITIVE_Y
        pitchRad = 0.0
        rollRad = 0.0
    }

    fun adapt(sample: PhoneSensorSample): VehicleImuSample {
        if (!isCalibrated) {
            throw IllegalStateException("vehicle frame is not calibrated")
        }
        // Extract raw acceleration along the phone axis aligned with the vehicle forward direction.
        // Forward acceleration is an internal chassis measurement that does NOT rotate with compass heading.
        val rawForward = when (deviceForwardAxis) {
            DeviceForwardAxis.POSITIVE_X -> sample.accelerationX.toDouble()
            DeviceForwardAxis.NEGATIVE_X -> -sample.accelerationX.toDouble()
            DeviceForwardAxis.POSITIVE_Y -> sample.accelerationY.toDouble()
            DeviceForwardAxis.NEGATIVE_Y -> -sample.accelerationY.toDouble()
            DeviceForwardAxis.POSITIVE_Z -> sample.accelerationZ.toDouble()
            DeviceForwardAxis.NEGATIVE_Z -> -sample.accelerationZ.toDouble()
        }
        // Static gravity compensation along the vehicle longitudinal axis (pitch angle)
        val gravityForwardOffset = 9.80665 * sin(pitchRad)
        val forwardAcceleration = rawForward - gravityForwardOffset

        return VehicleImuSample(
            timestampSeconds = sample.timestampNanos / NANOS_PER_SECOND,
            forwardAccelerationMps2 = forwardAcceleration,
            yawRateRps = sample.yawRateZ.toDouble(),
            location = sample.location,
        )
    }

    companion object {
        private const val NANOS_PER_SECOND = 1_000_000_000.0
    }
}
