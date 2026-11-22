package com.netscope.app

import java.net.SocketException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.security.cert.CertificateException

/**
 * Shared socket-error classification.
 *
 * Java does not expose portable errnos, so the classifier works
 * from exception types and, for SocketException, the message text
 * ("Connection reset", "Connection refused", ...), which the
 * Android runtime produces in English. The returned kinds are the
 * same vocabulary as the Python core's classifier: "reset",
 * "refused", "timeout", "unreachable", "dns", "error".
 *
 * Pure JVM (java.* only), so it is covered by the JVM unit tests.
 */

fun classifySocketError(exc: Throwable): String {
    return when (exc) {
        is SocketTimeoutException -> "timeout"
        is UnknownHostException -> "dns"
        is SocketException -> {
            val message = (exc.message ?: "").lowercase()
            when {
                "reset" in message || "aborted" in message || "broken pipe" in message -> "reset"
                "refused" in message -> "refused"
                "unreachable" in message || "no route to host" in message -> "unreachable"
                "timed out" in message || "timeout" in message -> "timeout"
                else -> "error"
            }
        }
        else -> "error"
    }
}

/** True when a certificate problem sits anywhere in the cause chain. */
fun hasCertificateCause(exc: Throwable): Boolean {
    var current: Throwable? = exc
    var depth = 0
    while (current != null && depth < 16) {
        if (current is CertificateException) return true
        current = current.cause
        depth += 1
    }
    return false
}
