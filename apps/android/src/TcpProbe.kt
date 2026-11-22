package com.netscope.app

import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket

/**
 * TCP connect probing, a port of the core's tcpprobe. Latency is
 * the time to complete a TCP connect; it needs no special
 * privileges and works the same everywhere.
 */

/** Connect to [target]:[port] several times and record each attempt. */
fun probeTcp(target: String, port: Int, attempts: Int = 4, timeoutSec: Double = 4.0): TcpResult {
    val results = ArrayList<TcpAttempt>()
    val timeoutMs = (timeoutSec * 1000).toInt()
    repeat(attempts) {
        val start = System.nanoTime()
        val socket = Socket()
        try {
            socket.connect(InetSocketAddress(target, port), timeoutMs)
            val latencyMs = (System.nanoTime() - start) / 1_000_000.0
            results.add(TcpAttempt(ok = true, latencyMs = latencyMs))
        } catch (exc: IOException) {
            results.add(
                TcpAttempt(ok = false, errorKind = classifySocketError(exc), error = exc.message)
            )
        } finally {
            try {
                socket.close()
            } catch (ignored: IOException) {
                // Nothing useful to do about a failed close.
            }
        }
    }
    return TcpResult(target, port, results)
}

/** One timed TCP connect; returns latency in ms, or null on failure. */
fun tcpConnectOnce(target: String, port: Int, timeoutMs: Int): Double? {
    val start = System.nanoTime()
    val socket = Socket()
    return try {
        socket.connect(InetSocketAddress(target, port), timeoutMs)
        (System.nanoTime() - start) / 1_000_000.0
    } catch (exc: IOException) {
        null
    } finally {
        try {
            socket.close()
        } catch (ignored: IOException) {
            // Nothing useful to do about a failed close.
        }
    }
}
