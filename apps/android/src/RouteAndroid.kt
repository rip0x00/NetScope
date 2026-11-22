package com.netscope.app

import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import android.system.StructPollfd
import java.io.FileDescriptor
import java.net.InetAddress

/**
 * The Android TTL-limited connect probe (used by RouteProbe.kt's
 * trace loop).
 *
 * java.net cannot set the unicast IP TTL, so the connect is done
 * with the operating-system calls in android.system: create a
 * socket, set IP_TTL, start a non-blocking connect, and poll for
 * completion with a timeout. A completed connect — or a refusal,
 * whose RST comes from the destination itself — proves the
 * destination answered at this TTL. ICMP replies cannot be read
 * without raw-socket permission, which Android applications do not
 * have, so intermediate hop addresses stay unknown; the result
 * model and the UI say so.
 *
 * Android-only (android.system), so this file is compiled by
 * build.sh against android.jar and excluded from the JVM tests.
 */

private fun ttlConnect(destination: String, port: Int, ttl: Int, timeoutMs: Int): Pair<Boolean, Double?> {
    var fd: FileDescriptor? = null
    return try {
        fd = Os.socket(OsConstants.AF_INET, OsConstants.SOCK_STREAM, 0)
        Os.setsockoptInt(fd, OsConstants.IPPROTO_IP, OsConstants.IP_TTL, ttl)
        Os.fcntlInt(fd, OsConstants.F_SETFL, OsConstants.O_NONBLOCK)
        val address = InetAddress.getByName(destination)
        val start = System.nanoTime()
        fun elapsed(): Double = (System.nanoTime() - start) / 1_000_000.0
        try {
            Os.connect(fd, address, port)
            Pair(true, elapsed())
        } catch (exc: ErrnoException) {
            when (exc.errno) {
                OsConstants.EINPROGRESS -> {
                    val pollFd = StructPollfd()
                    pollFd.fd = fd
                    pollFd.events = OsConstants.POLLOUT.toShort()
                    val ready = Os.poll(arrayOf(pollFd), timeoutMs)
                    val revents = pollFd.revents.toInt()
                    when {
                        ready <= 0 -> Pair(false, null) // timed out: silence at this TTL
                        revents and OsConstants.POLLERR == 0 &&
                            revents and OsConstants.POLLOUT != 0 ->
                            Pair(true, elapsed()) // connect completed
                        else -> {
                            // An error is pending (Os.getsockoptInt is not
                            // part of the public API). Asking connect again
                            // reports the real outcome: ECONNREFUSED means
                            // the destination itself answered with a reset.
                            try {
                                Os.connect(fd, address, port)
                                Pair(true, elapsed())
                            } catch (again: ErrnoException) {
                                when (again.errno) {
                                    OsConstants.ECONNREFUSED,
                                    OsConstants.EISCONN -> Pair(true, elapsed())
                                    else -> Pair(false, null)
                                }
                            }
                        }
                    }
                }
                OsConstants.ECONNREFUSED -> Pair(true, elapsed())
                else -> Pair(false, null)
            }
        }
    } catch (exc: Exception) {
        Pair(false, null)
    } finally {
        if (fd != null) {
            try {
                Os.close(fd)
            } catch (ignored: Exception) {
                // Nothing useful to do about a failed close.
            }
        }
    }
}

private val androidTtlProbe = TtlConnectProbe { destination, port, ttl, timeoutMs ->
    ttlConnect(destination, port, ttl, timeoutMs)
}

/** Trace the route to [host] using the Android TTL connect probe. */
fun probeRouteAndroid(host: String, maxHops: Int = 30, port: Int = 443, timeoutMs: Int = 1500): RouteResult =
    probeRouteWith(host, maxHops, port, timeoutMs, androidTtlProbe)
