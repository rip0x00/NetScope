package com.netscope.app

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.sqrt

/**
 * Latency statistics, jitter, and packet-loss accounting.
 *
 * A port of the Python core's stats module
 * (shared/core/src/netscope_core/stats.py). The definitions are the
 * shared cross-platform ones, so figures stay comparable between
 * reports on every platform:
 *
 * - Percentiles use linear interpolation between closest ranks: the
 *   rank of percentile `p` over `n` sorted samples is
 *   `p/100 * (n - 1)`, interpolated between the neighbouring samples.
 * - Standard deviation is the population standard deviation: the
 *   series being summarised is the complete set of measurements
 *   taken, not a sample drawn from a larger population.
 * - Jitter: `jitterAvg` is the mean absolute difference between
 *   consecutive samples and `jitterMax` is the largest such
 *   difference (the successive-difference measure in the style of
 *   the RFC 3550 jitter estimator, reported as a plain average so
 *   the figure can be reproduced from the raw samples alone).
 *
 * Pure JVM — no Android APIs — so it is covered by the JVM unit
 * tests in tests/.
 */

data class LatencyStats(
    val count: Int = 0,
    val min: Double? = null,
    val max: Double? = null,
    val avg: Double? = null,
    val median: Double? = null,
    val p90: Double? = null,
    val p95: Double? = null,
    val p99: Double? = null,
    val stddev: Double? = null,
    val jitterAvg: Double? = null,
    val jitterMax: Double? = null
)

private fun percentile(sortedSamples: List<Double>, p: Double): Double {
    if (sortedSamples.size == 1) return sortedSamples[0]
    val rank = (p / 100.0) * (sortedSamples.size - 1)
    val low = floor(rank).toInt()
    val high = ceil(rank).toInt()
    if (low == high) return sortedSamples[rank.toInt()]
    val fraction = rank - low
    return sortedSamples[low] + fraction * (sortedSamples[high] - sortedSamples[low])
}

/**
 * (average, maximum) absolute successive difference of [samples].
 * Returns (null, null) when fewer than two samples exist, because no
 * successive difference is defined.
 */
fun jitterOf(samples: List<Double>): Pair<Double?, Double?> {
    if (samples.size < 2) return Pair(null, null)
    val diffs = ArrayList<Double>(samples.size - 1)
    for (i in 1 until samples.size) diffs.add(abs(samples[i] - samples[i - 1]))
    return Pair(diffs.average(), diffs.maxOrNull())
}

/** Compute the full latency distribution for a series of samples. */
fun latencyStats(samples: List<Double>): LatencyStats {
    if (samples.isEmpty()) return LatencyStats(count = 0)
    val ordered = samples.sorted()
    val count = samples.size
    val mean = samples.average()
    var squared = 0.0
    for (value in samples) squared += (value - mean) * (value - mean)
    val (jitterAvg, jitterMax) = jitterOf(samples)
    return LatencyStats(
        count = count,
        min = ordered.first(),
        max = ordered.last(),
        avg = mean,
        median = percentile(ordered, 50.0),
        p90 = percentile(ordered, 90.0),
        p95 = percentile(ordered, 95.0),
        p99 = percentile(ordered, 99.0),
        stddev = sqrt(squared / count),
        jitterAvg = jitterAvg,
        jitterMax = jitterMax
    )
}

/** Packet-loss accounting for one probe series. */
data class PacketLoss(val sent: Int = 0, val received: Int = 0, val timeouts: Int = 0) {
    val lossPercent: Double
        get() = if (sent == 0) 0.0 else 100.0 * (sent - received) / sent
}

/**
 * Build a [PacketLoss] from raw counters. `received` is clamped to
 * `sent`; a probe that records more responses than probes sent has a
 * bookkeeping bug, and the loss figure must not go negative to hide
 * it.
 */
fun packetLoss(sent: Int, received: Int, timeouts: Int = 0): PacketLoss =
    PacketLoss(sent = sent, received = received.coerceIn(0, maxOf(sent, 0)), timeouts = timeouts)
