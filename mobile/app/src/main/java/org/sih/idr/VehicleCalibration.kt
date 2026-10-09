package org.sih.idr

import android.location.Location
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.hypot
import kotlin.math.sqrt

enum class CalibrationStage {
    STATIONARY,
    FORWARD_MOTION,
    COMPLETE,
    FAILED,
}

data class CalibrationResult(
    val pitchRad: Double,
    val rollRad: Double,
    val vehicleHeadingRad: Double,
    val forwardAxis: DeviceForwardAxis,
)

class VehicleCalibration(
    private val stationarySampleTarget: Int = 50,
    private val motionSampleTarget: Int = 10,
    private val stationaryVarianceLimit: Double = 0.8,
    private val minimumMotionSpeedMps: Float = 2.0f,
) {
    private val stationarySamples = mutableListOf<PhoneSensorSample>()
    private val motionSamples = mutableListOf<PhoneSensorSample>()
    var stage: CalibrationStage = CalibrationStage.STATIONARY
        private set

    init {
        require(stationarySampleTarget > 1) { "stationary sample target must exceed one" }
        require(motionSampleTarget > 1) { "motion sample target must exceed one" }
        require(stationaryVarianceLimit > 0.0) { "variance limit must be positive" }
    }

    fun reset() {
        stationarySamples.clear()
        motionSamples.clear()
        stage = CalibrationStage.STATIONARY
    }

    fun observe(sample: PhoneSensorSample): CalibrationResult? {
        if (stage == CalibrationStage.COMPLETE || stage == CalibrationStage.FAILED) {
            return null
        }
        when (stage) {
            CalibrationStage.STATIONARY -> observeStationary(sample)
            CalibrationStage.FORWARD_MOTION -> observeMotion(sample)
            else -> Unit
        }
        return if (stage == CalibrationStage.COMPLETE) buildResult() else null
    }

    private fun observeStationary(sample: PhoneSensorSample) {
        stationarySamples += sample
        if (stationarySamples.size < stationarySampleTarget) return
        val magnitudes = stationarySamples.map { accelerationMagnitude(it) }
        val mean = magnitudes.average()
        val variance = magnitudes.sumOf { (it - mean) * (it - mean) } / magnitudes.size
        if (variance > stationaryVarianceLimit) {
            stage = CalibrationStage.FAILED
            return
        }
        stage = CalibrationStage.FORWARD_MOTION
    }

    private fun observeMotion(sample: PhoneSensorSample) {
        val location = sample.location
        if (
            location == null ||
            !location.hasBearing() ||
            !location.hasSpeed() ||
            location.speed < minimumMotionSpeedMps
        ) {
            return
        }
        motionSamples += sample
        if (motionSamples.size >= motionSampleTarget) {
            stage = CalibrationStage.COMPLETE
        }
    }

    private fun buildResult(): CalibrationResult {
        val stationary = stationarySamples.last()
        val pitch = atan2(
            -stationary.accelerationX.toDouble(),
            hypot(stationary.accelerationY.toDouble(), stationary.accelerationZ.toDouble()),
        )
        val roll = atan2(
            stationary.accelerationY.toDouble(),
            stationary.accelerationZ.toDouble(),
        )
        val bearingRad = Math.toRadians(motionSamples.mapNotNull { it.location?.bearing?.toDouble() }.average())
        val forwardAcceleration = motionSamples.map {
            val correctedX = it.accelerationX - stationary.accelerationX
            val correctedY = it.accelerationY - stationary.accelerationY
            hypot(correctedX, correctedY)
        }.average()
        val axis = if (abs(motionSamples.map { it.accelerationX }.average()) >=
            abs(motionSamples.map { it.accelerationY }.average())
        ) {
            DeviceForwardAxis.POSITIVE_X
        } else {
            DeviceForwardAxis.POSITIVE_Y
        }
        if (!forwardAcceleration.isFinite() || !bearingRad.isFinite()) {
            stage = CalibrationStage.FAILED
            throw IllegalStateException("calibration produced a non-finite result")
        }
        return CalibrationResult(pitch, roll, bearingRad, axis)
    }

    private fun accelerationMagnitude(sample: PhoneSensorSample): Double =
        sqrt(
            sample.accelerationX * sample.accelerationX +
                sample.accelerationY * sample.accelerationY +
                sample.accelerationZ * sample.accelerationZ,
        ).toDouble()
}
