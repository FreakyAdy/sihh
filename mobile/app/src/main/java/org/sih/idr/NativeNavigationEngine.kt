package org.sih.idr

import android.location.Location
import org.json.JSONObject
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin

enum class NativeNavigationMode {
    INITIALIZING,
    GNSS_AIDED,
    DEAD_RECKONING,
}

data class NativeNavigationEstimate(
    val timestampSeconds: Double,
    val latitude: Double?,
    val longitude: Double?,
    val speedMps: Double,
    val headingRad: Double,
    val mode: NativeNavigationMode,
    val confidence: Double,
)

interface SpeedCorrectionModel {
    fun predictSpeed(forwardAccelerationMps2: Double, yawRateRps: Double): Double
}

class LinearSpeedCorrectionModel(
    private val bias: Double = 0.0,
    private val accelerationWeight: Double = 0.0,
    private val yawRateWeight: Double = 0.0,
    private val absoluteAccelerationWeight: Double = 0.0,
) : SpeedCorrectionModel {
    companion object {
        fun fromJson(json: String): LinearSpeedCorrectionModel {
            val payload = JSONObject(json)
            require(payload.optString("model_type") == "linear_speed_correction") {
                "unsupported speed model type"
            }
            require(payload.optString("version").isNotBlank()) {
                "model version is required"
            }
            val names = payload.getJSONArray("feature_names")
            val weights = payload.getJSONArray("weights")
            require(names.length() == weights.length()) {
                "feature and weight lengths must match"
            }
            val values = (0 until names.length()).associate {
                names.getString(it) to weights.getDouble(it)
            }
            require(values.keys == setOf(
                "bias",
                "forward_acceleration_mps2",
                "yaw_rate_rps",
                "absolute_acceleration_mps2",
            )) {
                "model feature names do not match the runtime contract"
            }
            return LinearSpeedCorrectionModel(
                bias = values["bias"] ?: 0.0,
                accelerationWeight = values["forward_acceleration_mps2"] ?: 0.0,
                yawRateWeight = values["yaw_rate_rps"] ?: 0.0,
                absoluteAccelerationWeight = values["absolute_acceleration_mps2"] ?: 0.0,
            )
        }
    }

    override fun predictSpeed(forwardAccelerationMps2: Double, yawRateRps: Double): Double =
        max(
            0.0,
            bias +
                accelerationWeight * forwardAccelerationMps2 +
                yawRateWeight * yawRateRps +
                absoluteAccelerationWeight * kotlin.math.abs(forwardAccelerationMps2),
        )
}

class NativeNavigationEngine(
    private val speedModel: SpeedCorrectionModel = LinearSpeedCorrectionModel(),
    private val outageConfirmSeconds: Double = 0.2,
    private val recoveryConfirmCount: Int = 2,
    private val confidenceDecaySeconds: Double = 60.0,
) {
    private var origin: Location? = null
    private var lastTimestampSeconds: Double? = null
    private var outageStartSeconds: Double? = null
    private var recoveryCount = 0
    private var xMeters = 0.0
    private var yMeters = 0.0
    private var speedMps = 0.0
    private var headingRad = 0.0
    private var mode = NativeNavigationMode.INITIALIZING

    fun reset() {
        origin = null
        lastTimestampSeconds = null
        outageStartSeconds = null
        recoveryCount = 0
        xMeters = 0.0
        yMeters = 0.0
        speedMps = 0.0
        headingRad = 0.0
        mode = NativeNavigationMode.INITIALIZING
    }

    fun update(sample: VehicleImuSample): NativeNavigationEstimate {
        require(sample.timestampSeconds.isFinite()) { "sample timestamp must be finite" }
        require(sample.forwardAccelerationMps2.isFinite()) {
            "forward acceleration must be finite"
        }
        require(sample.yawRateRps.isFinite()) { "yaw rate must be finite" }
        val previousTimestamp = lastTimestampSeconds
        val dt = if (previousTimestamp == null) 0.0 else {
            sample.timestampSeconds - previousTimestamp
        }
        require(dt >= 0.0) { "sample timestamps must be non-decreasing" }
        require(dt <= MAX_INTERVAL_SECONDS) { "sample timestamp gap exceeds engine limit" }
        lastTimestampSeconds = sample.timestampSeconds

        headingRad += sample.yawRateRps * dt
        val modelSpeed = speedModel.predictSpeed(
            sample.forwardAccelerationMps2,
            sample.yawRateRps,
        )
        speedMps = max(
            0.0,
            speedMps + sample.forwardAccelerationMps2 * dt,
        ).coerceAtMost(max(modelSpeed, speedMps + MAX_SPEED_STEP_MPS))
        val distance = speedMps * dt
        xMeters += cos(headingRad) * distance
        yMeters += sin(headingRad) * distance

        val location = sample.location
        if (location != null) {
            applyGnss(location, sample.timestampSeconds)
        } else {
            enterDeadReckoning(sample.timestampSeconds)
        }
        return estimate(sample.timestampSeconds)
    }

    private fun applyGnss(location: Location, timestampSeconds: Double) {
        if (origin == null) {
            origin = Location(location)
            xMeters = 0.0
            yMeters = 0.0
            if (location.hasBearing()) headingRad = Math.toRadians(location.bearing.toDouble())
            mode = NativeNavigationMode.GNSS_AIDED
            recoveryCount = recoveryConfirmCount
        } else {
            recoveryCount += 1
            if (mode != NativeNavigationMode.DEAD_RECKONING ||
                recoveryCount >= recoveryConfirmCount
            ) {
                projectLocation(location)
                mode = NativeNavigationMode.GNSS_AIDED
                outageStartSeconds = null
            }
        }
        if (location.hasSpeed()) speedMps = max(0.0, location.speed.toDouble())
    }

    private fun enterDeadReckoning(timestampSeconds: Double) {
        if (origin == null) return
        recoveryCount = 0
        if (outageStartSeconds == null) outageStartSeconds = timestampSeconds
        if (timestampSeconds - outageStartSeconds!! >= outageConfirmSeconds) {
            mode = NativeNavigationMode.DEAD_RECKONING
        }
    }

    private fun projectLocation(location: Location) {
        val reference = origin ?: return
        val distance = reference.distanceTo(location).toDouble()
        val bearing = Math.toRadians(reference.bearingTo(location).toDouble())
        xMeters = distance * cos(bearing)
        yMeters = distance * sin(bearing)
    }

    private fun estimate(timestampSeconds: Double): NativeNavigationEstimate {
        val reference = origin
        val latitude = reference?.latitude
        // Heading zero is north: x is northing and y is easting.
        val adjustedLatitude = reference?.let { it.latitude + xMeters / METERS_PER_DEGREE }
        val longitude = reference?.let {
            it.longitude + yMeters / (METERS_PER_DEGREE * cos(Math.toRadians(it.latitude)))
        }
        val confidence = if (mode == NativeNavigationMode.DEAD_RECKONING) {
            val duration = timestampSeconds - (outageStartSeconds ?: timestampSeconds)
            (1.0 - duration / confidenceDecaySeconds).coerceIn(0.0, 1.0)
        } else {
            1.0
        }
        return NativeNavigationEstimate(
            timestampSeconds = timestampSeconds,
            latitude = adjustedLatitude ?: latitude,
            longitude = longitude,
            speedMps = speedMps,
            headingRad = headingRad,
            mode = mode,
            confidence = confidence,
        )
    }

    companion object {
        private const val MAX_INTERVAL_SECONDS = 1.0
        private const val MAX_SPEED_STEP_MPS = 5.0
        private const val METERS_PER_DEGREE = 111_320.0
    }
}
