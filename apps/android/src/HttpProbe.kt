package com.netscope.app

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.MalformedURLException
import java.net.URL
import java.security.MessageDigest
import javax.net.ssl.SSLException

/**
 * HTTP/HTTPS fetching with redirect following and block-page
 * detection, a port of the core's httpprobe.
 *
 * Filtering products and ISPs often answer blocked requests with an
 * ordinary-looking HTTP response — a warning page, a redirect to a
 * notice, or a 403/451 status. This module fetches the page the way
 * a browser would and scans the body for known markers of such
 * pages.
 */

const val USER_AGENT =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 NetScope/0.4"

// Substrings (lowercase) commonly found on ISP and filtering block
// pages. Matching is deliberately conservative: a marker is
// evidence, not proof, and the verdict layer weighs it accordingly.
// The list is identical to the Python core's BLOCK_MARKERS.
val BLOCK_MARKERS = listOf(
    "access denied",
    "access to this site has been blocked",
    "this site has been blocked",
    "this website has been blocked",
    "site blocked",
    "content blocked",
    "blocked by",
    "web filtering",
    "internet filtering",
    "request blocked",
    // Persian markers, as served by Iranian ISP block pages.
    "فیلترینگ",
    "مسدود شده است",
    "دسترسی به این تارنما",
    "دسترسی به این سایت"
)

private const val SCAN_BYTES = 65536
private const val READ_BYTES = 1024 * 1024
private val REDIRECT_STATUSES = setOf(301, 302, 303, 307, 308)

/** Return the block-page markers present in [text]. */
fun findBlockMarkers(text: String): List<String> {
    val lowered = text.lowercase()
    return BLOCK_MARKERS.filter { it in lowered }
}

private class FetchOutcome(
    val status: Int,
    val reason: String?,
    val location: String?,
    val body: ByteArray
)

private fun fetchOnce(url: String, timeoutSec: Double): FetchOutcome {
    val connection = URL(url).openConnection() as HttpURLConnection
    try {
        connection.instanceFollowRedirects = false
        connection.requestMethod = "GET"
        connection.connectTimeout = (timeoutSec * 1000).toInt()
        connection.readTimeout = (timeoutSec * 1000).toInt()
        connection.setRequestProperty("User-Agent", USER_AGENT)
        connection.setRequestProperty("Accept", "*/*")
        val status = connection.responseCode
        val reason = connection.responseMessage
        val location = connection.getHeaderField("Location")
        val stream = if (status >= 400) connection.errorStream else connection.inputStream
        val body = ByteArrayOutputStream()
        if (stream != null) {
            val buffer = ByteArray(8192)
            var total = 0
            while (total < READ_BYTES) {
                val want = minOf(buffer.size, READ_BYTES - total)
                val read = stream.read(buffer, 0, want)
                if (read < 0) break
                body.write(buffer, 0, read)
                total += read
            }
            stream.close()
        }
        return FetchOutcome(status, reason, location, body.toByteArray())
    } finally {
        connection.disconnect()
    }
}

private fun sha256Hex(bytes: ByteArray): String {
    val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
    return digest.joinToString("") { "%02x".format(it) }
}

/** Fetch `scheme://hostname/`, following up to [maxRedirects] redirects. */
fun probeHttp(
    hostname: String,
    scheme: String = "https",
    timeoutSec: Double = 10.0,
    maxRedirects: Int = 5
): HttpResult {
    val url = "$scheme://$hostname/"
    val start = System.nanoTime()
    var redirects = 0
    var current = url
    fun elapsedMs(): Double = (System.nanoTime() - start) / 1_000_000.0
    return try {
        while (true) {
            val outcome = fetchOnce(current, timeoutSec)
            if (outcome.status in REDIRECT_STATUSES && outcome.location != null && redirects < maxRedirects) {
                current = URL(URL(current), outcome.location).toString()
                redirects += 1
                continue
            }
            return HttpResult(
                scheme = scheme, url = url, ok = true,
                status = outcome.status, reason = outcome.reason,
                finalUrl = current, redirects = redirects,
                sizeBytes = outcome.body.size,
                bodySha256 = sha256Hex(outcome.body),
                markers = findBlockMarkers(
                    String(outcome.body.copyOf(minOf(SCAN_BYTES, outcome.body.size)), Charsets.UTF_8)
                ),
                latencyMs = elapsedMs()
            )
        }
        @Suppress("UNREACHABLE_CODE")
        HttpResult(scheme = scheme, url = url) // loop always returns or throws
    } catch (exc: SSLException) {
        val kind = if (hasCertificateCause(exc)) "certificate" else "protocol"
        HttpResult(
            scheme = scheme, url = url, redirects = redirects,
            latencyMs = elapsedMs(), errorKind = kind, error = exc.message
        )
    } catch (exc: MalformedURLException) {
        HttpResult(
            scheme = scheme, url = url, redirects = redirects,
            latencyMs = elapsedMs(), errorKind = "error", error = exc.message
        )
    } catch (exc: IOException) {
        HttpResult(
            scheme = scheme, url = url, redirects = redirects,
            latencyMs = elapsedMs(), errorKind = classifySocketError(exc), error = exc.message
        )
    }
}
