package org.sih.idr

import kotlin.math.cos
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
}

class VehicleFrameAdapter {
    private var vehicleHeadingRad: Double? = null
    private var deviceForwardAxis = DeviceForwardAxis.POSITIVE_Y

    fun configure(
        vehicleHeadingRad: Double,
        forwardAxis: DeviceForwardAxis = DeviceForwardAxis.POSITIVE_Y,
    ) {
        require(vehicleHeadingRad.isFinite()) { "vehicle heading must be finite" }
        this.vehicleHeadingRad = vehicleHeadingRad
        this.deviceForwardAxis = forwardAxis
    }

    fun isConfigured(): Boolean = vehicleHeadingRad != null

    fun reset() {
        vehicleHeadingRad = null
        deviceForwardAxis = DeviceForwardAxis.POSITIVE_Y
    }

    fun adapt(sample: PhoneSensorSample): VehicleImuSample {
        val heading = vehicleHeadingRad
            ?: throw IllegalStateException("vehicle frame is not calibrated")
        val deviceForward = when (deviceForwardAxis) {
            DeviceForwardAxis.POSITIVE_X -> 0.0
            DeviceForwardAxis.NEGATIVE_X -> Math.PI
            DeviceForwardAxis.POSITIVE_Y -> Math.PI / 2.0
            DeviceForwardAxis.NEGATIVE_Y -> -Math.PI / 2.0
        }
        val projectionAngle = heading - deviceForward
        val forwardX = cos(projectionAngle)
        val forwardY = sin(projectionAngle)
        val forwardAcceleration =
            sample.accelerationX * forwardX + sample.accelerationY * forwardY
        return VehicleImuSample(
            timestampSeconds = sample.timestampNanos / NANOS_PER_SECOND,
            forwardAccelerationMps2 = forwardAcceleration.toDouble(),
            yawRateRps = sample.yawRateZ.toDouble(),
            location = sample.location,
        )
    }

    companion object {
        private const val NANOS_PER_SECOND = 1_000_000_000.0
    }
}
