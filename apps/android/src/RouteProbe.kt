package com.netscope.app

import java.net.InetAddress

/**
 * Route probing: where on the path to a host do packets stop?
 *
 * This file is the platform-independent part: the result model,
 * the stop-point classification, and the trace loop — a direct
 * port of the Python core's routeprobe (classify_route and the
 * _trace_tcp loop, including its stop after 5 consecutive silent
 * TTLs). The actual TTL-limited connect is platform work: Android
 * applications cannot open raw sockets (so no ICMP method) and the
 * TTL has to be set through the operating system; RouteAndroid.kt
 * supplies that probe. The method is recorded on the result and
 * stated in the UI: this is a reachability trace, not a full
 * traceroute.
 */

private const val MAX_SILENT_HOPS = 5

data class RouteHop(
    val ttl: Int,
    val ip: String? = null,
    val rttMs: Double? = null
) {
    val responded: Boolean
        get() = ip != null
}

class RouteResult(
    val host: String,
    val destinationIp: String?,
    val method: String, // "tcp" on Android (ICMP needs raw sockets)
    val hops: List<RouteHop> = emptyList(),
    val reached: Boolean = false,
    val stopPoint: String = "no-response", // destination | local | mid-path | no-response
    val note: String = "",
    val error: String? = null
) {
    val lastRespondingTtl: Int?
        get() = hops.lastOrNull { it.responded }?.ttl
}

/**
 * Classify where a trace stopped. Returns (stop_point, note).
 * Pure function of the recorded hops — a direct port of the core's
 * classify_route — so it is covered by the JVM unit tests.
 */
fun classifyRoute(hops: List<RouteHop>, reached: Boolean, method: String): Pair<String, String> {
    val last = hops.lastOrNull { it.responded }?.ttl
    if (reached) {
        val where = if (last != null) "hop $last" else "the destination"
        return Pair("destination", "The destination answered at $where; the full path responded.")
    }
    if (last == null) {
        val note = if (method == "tcp") {
            "No probe was answered at any TTL. Hop addresses cannot be read without " +
                "raw-socket permission (the TCP fallback was in use), so the trace can only " +
                "say that the destination never answered."
        } else {
            "No hop answered at any TTL; the path is silent from the first router onward."
        }
        return Pair("no-response", note)
    }
    if (last <= 3) {
        return Pair(
            "local",
            "Answers stop at hop $last, inside or just past the local network. " +
                "The problem is likely close to home: the router, the ISP's first hops, " +
                "or a local firewall."
        )
    }
    var note = "Answers stop at hop $last, partway to the destination. Routers beyond that " +
        "point either drop the probes or do not answer them; the break is on the path, " +
        "not at the destination."
    if (method == "tcp") {
        note += " Hop addresses are unknown because ICMP replies cannot be read without " +
            "raw-socket permission."
    }
    return Pair("mid-path", note)
}

/**
 * One TTL-limited connect probe: returns (answered, latency_ms).
 * "Answered" means the destination itself responded at this TTL —
 * a completed connect, or a refusal (the RST comes from the
 * destination). Implemented by the platform layer.
 */
fun interface TtlConnectProbe {
    fun probe(destination: String, port: Int, ttl: Int, timeoutMs: Int): Pair<Boolean, Double?>
}

/**
 * The trace loop: probe TTLs 1..maxHops until the destination
 * answers or 5 consecutive TTLs stay silent (the core's rule).
 */
fun traceTcp(
    destination: String,
    port: Int,
    maxHops: Int,
    timeoutMs: Int,
    probe: TtlConnectProbe
): Pair<List<RouteHop>, Boolean> {
    val hops = ArrayList<RouteHop>()
    var reached = false
    var silent = 0
    for (ttl in 1..maxHops) {
        val (answered, latency) = probe.probe(destination, port, ttl, timeoutMs)
        if (answered) {
            hops.add(RouteHop(ttl = ttl, ip = destination, rttMs = latency))
            reached = true
        } else {
            hops.add(RouteHop(ttl = ttl))
        }
        if (reached) break
        silent += 1
        if (silent >= MAX_SILENT_HOPS) break
    }
    return Pair(hops, reached)
}

/** Resolve [host] and trace to it with the platform [probe]. */
fun probeRouteWith(
    host: String,
    maxHops: Int = 30,
    port: Int = 443,
    timeoutMs: Int = 1500,
    probe: TtlConnectProbe
): RouteResult {
    val destination = try {
        InetAddress.getAllByName(host).firstOrNull { it.address.size == 4 }?.hostAddress
    } catch (exc: Exception) {
        null
    }
    if (destination == null) {
        return RouteResult(
            host = host,
            destinationIp = null,
            method = "tcp",
            error = "could not resolve $host to an IPv4 address",
            note = "NetScope could not resolve $host to an IPv4 address, so no route could be traced."
        )
    }
    val (hops, reached) = traceTcp(destination, port, maxHops, timeoutMs, probe)
    val (stopPoint, note) = classifyRoute(hops, reached, "tcp")
    return RouteResult(
        host = host,
        destinationIp = destination,
        method = "tcp",
        hops = hops,
        reached = reached,
        stopPoint = stopPoint,
        note = note
    )
}
