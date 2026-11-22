package com.netscope.app

/**
 * DNS wire format: query encoder and response parser.
 *
 * A port of the Python core's dnsprobe wire code
 * (shared/core/src/netscope_core/dnsprobe.py). Record types A, AAAA,
 * CNAME, NS, MX, TXT, SOA, PTR, SRV and CAA have proper rdata
 * decoding, matching the core's presentation forms; unknown types
 * are carried as hex with a `TYPE<n>` name, never dropped. Malformed
 * packets raise IllegalArgumentException, matching the Python
 * parser's ValueError.
 *
 * Pure JVM — no Android APIs — so it is covered by the JVM unit
 * tests in tests/.
 */

const val QTYPE_A = 1
const val QTYPE_NS = 2
const val QTYPE_CNAME = 5
const val QTYPE_SOA = 6
const val QTYPE_PTR = 12
const val QTYPE_MX = 15
const val QTYPE_TXT = 16
const val QTYPE_AAAA = 28
const val QTYPE_SRV = 33
const val QTYPE_CAA = 257

private val TYPE_NAMES = mapOf(
    QTYPE_A to "A",
    QTYPE_NS to "NS",
    QTYPE_CNAME to "CNAME",
    QTYPE_SOA to "SOA",
    QTYPE_PTR to "PTR",
    QTYPE_MX to "MX",
    QTYPE_TXT to "TXT",
    QTYPE_AAAA to "AAAA",
    QTYPE_SRV to "SRV",
    QTYPE_CAA to "CAA"
)

/** Record type code for a type name ("A", "MX", ...), or null. */
fun qtypeForName(name: String): Int? = TYPE_NAMES.entries.firstOrNull { it.value == name }?.key

val RCODE_NAMES = mapOf(0 to "NOERROR", 1 to "FORMERR", 2 to "SERVFAIL", 3 to "NXDOMAIN", 5 to "REFUSED")

private fun u16(data: ByteArray, offset: Int): Int =
    ((data[offset].toInt() and 0xFF) shl 8) or (data[offset + 1].toInt() and 0xFF)

private fun u32(data: ByteArray, offset: Int): Long =
    ((data[offset].toInt() and 0xFF).toLong() shl 24) or
        ((data[offset + 1].toInt() and 0xFF).toLong() shl 16) or
        ((data[offset + 2].toInt() and 0xFF).toLong() shl 8) or
        (data[offset + 3].toInt() and 0xFF).toLong()

private fun putU16(out: ByteArray, offset: Int, value: Int) {
    out[offset] = (value shr 8).toByte()
    out[offset + 1] = value.toByte()
}

fun encodeName(name: String): ByteArray {
    val out = ArrayList<Byte>()
    for (label in name.trimEnd('.').split(".")) {
        val encoded = label.toByteArray(Charsets.UTF_8)
        require(encoded.size <= 63) { "DNS label too long: '$label'" }
        out.add(encoded.size.toByte())
        for (b in encoded) out.add(b)
    }
    out.add(0)
    return ByteArray(out.size) { out[it] }
}

/** Build a single-question DNS query packet (recursion desired). */
fun buildQuery(name: String, qtype: Int, txid: Int): ByteArray {
    val nameBytes = encodeName(name)
    val packet = ByteArray(12 + nameBytes.size + 4)
    putU16(packet, 0, txid)
    putU16(packet, 2, 0x0100)
    putU16(packet, 4, 1)
    nameBytes.copyInto(packet, 12)
    putU16(packet, 12 + nameBytes.size, qtype)
    putU16(packet, 12 + nameBytes.size + 2, 1)
    return packet
}

/**
 * Read a possibly compressed domain name at [offset].
 * Returns the name and the offset just past it (past the compression
 * pointer if one was followed, as in the Python implementation).
 */
fun readName(data: ByteArray, offset: Int): Pair<String, Int> {
    val labels = ArrayList<String>()
    var jumped = false
    var nextOffset = offset
    var jumps = 0
    var pos = offset
    while (true) {
        require(pos < data.size) { "name runs past end of packet" }
        val length = data[pos].toInt() and 0xFF
        if (length == 0) {
            if (!jumped) nextOffset = pos + 1
            break
        }
        if (length and 0xC0 == 0xC0) {
            require(pos + 1 < data.size) { "truncated compression pointer" }
            val pointer = ((length and 0x3F) shl 8) or (data[pos + 1].toInt() and 0xFF)
            if (!jumped) nextOffset = pos + 2
            pos = pointer
            jumped = true
            jumps += 1
            require(jumps <= 128) { "compression pointer loop" }
            continue
        }
        require(length and 0xC0 == 0) { "reserved label bits set" }
        val start = pos + 1
        val end = start + length
        require(end <= data.size) { "label runs past end of packet" }
        labels.add(String(data, start, length, Charsets.UTF_8))
        pos = end
    }
    return Pair(labels.joinToString("."), nextOffset)
}

data class DnsRecord(val name: String, val type: String, val value: String, val ttl: Long)

class DnsMessage(
    val txid: Int,
    val rcode: Int,
    val answers: List<DnsRecord>,
    val authority: List<DnsRecord> = emptyList()
) {

    val rcodeName: String
        get() = RCODE_NAMES[rcode] ?: "RCODE$rcode"

    /** A/AAAA values for [name], following CNAME chains in the message. */
    fun addressesFor(name: String): List<String> {
        val result = ArrayList<String>()
        var current = name.trimEnd('.').lowercase()
        val seen = HashSet<String>()
        while (current.isNotEmpty() && current !in seen) {
            seen.add(current)
            var nextName: String? = null
            for (record in answers) {
                if (record.name.trimEnd('.').lowercase() != current) continue
                if (record.type == "A" || record.type == "AAAA") {
                    if (record.value !in result) result.add(record.value)
                } else if (record.type == "CNAME") {
                    nextName = record.value.trimEnd('.').lowercase()
                }
            }
            current = nextName ?: ""
        }
        return result
    }
}

private fun formatIpv4(data: ByteArray, offset: Int): String =
    (0..3).joinToString(".") { (data[offset + it].toInt() and 0xFF).toString() }

private fun formatIpv6(data: ByteArray, offset: Int): String {
    val groups = IntArray(8) { u16(data, offset + it * 2) }
    // Find the longest run of zero groups (length >= 2) to compress.
    var bestStart = -1
    var bestLen = 0
    var curStart = -1
    var curLen = 0
    for (i in 0..7) {
        if (groups[i] == 0) {
            if (curStart == -1) curStart = i
            curLen += 1
            if (curLen > bestLen) {
                bestLen = curLen
                bestStart = curStart
            }
        } else {
            curStart = -1
            curLen = 0
        }
    }
    if (bestLen < 2) bestStart = -1
    val sb = StringBuilder()
    var i = 0
    while (i < 8) {
        if (i == bestStart) {
            if (sb.isEmpty() || sb[sb.length - 1] != ':') sb.append(':')
            sb.append(':')
            i += bestLen
            continue
        }
        if (sb.isNotEmpty() && sb[sb.length - 1] != ':') sb.append(':')
        sb.append(groups[i].toString(16))
        i += 1
    }
    return if (sb.isEmpty()) "::" else sb.toString()
}

/** Decode one record's rdata to its presentation form (core semantics). */
private fun parseRdata(data: ByteArray, rtype: Int, start: Int, rdlen: Int): String {
    val end = start + rdlen
    when (rtype) {
        QTYPE_A -> if (rdlen == 4) return formatIpv4(data, start)
        QTYPE_AAAA -> if (rdlen == 16) return formatIpv6(data, start)
        QTYPE_CNAME, QTYPE_NS, QTYPE_PTR -> {
            val (value, _) = readName(data, start)
            return value
        }
        QTYPE_MX -> {
            require(rdlen >= 3) { "truncated MX rdata" }
            val preference = u16(data, start)
            val (exchange, _) = readName(data, start + 2)
            return "$preference $exchange"
        }
        QTYPE_TXT -> {
            val parts = StringBuilder()
            var pos = start
            while (pos < end) {
                val size = data[pos].toInt() and 0xFF
                pos += 1
                require(pos + size <= end) { "truncated TXT string" }
                parts.append(String(data, pos, size, Charsets.UTF_8))
                pos += size
            }
            return parts.toString()
        }
        QTYPE_SOA -> {
            val (mname, afterMname) = readName(data, start)
            val (rname, afterRname) = readName(data, afterMname)
            require(afterRname + 20 <= end) { "truncated SOA rdata" }
            val numbers = (0 until 5).joinToString(" ") { u32(data, afterRname + it * 4).toString() }
            return "$mname $rname $numbers"
        }
        QTYPE_SRV -> {
            require(rdlen >= 7) { "truncated SRV rdata" }
            val priority = u16(data, start)
            val weight = u16(data, start + 2)
            val port = u16(data, start + 4)
            val (target, _) = readName(data, start + 6)
            return "$priority $weight $port $target"
        }
        QTYPE_CAA -> {
            require(rdlen >= 2) { "truncated CAA rdata" }
            val flags = data[start].toInt() and 0xFF
            val tagLength = data[start + 1].toInt() and 0xFF
            require(2 + tagLength <= rdlen) { "truncated CAA tag" }
            val tag = String(data, start + 2, tagLength, Charsets.US_ASCII)
            val value = String(data, start + 2 + tagLength, rdlen - 2 - tagLength, Charsets.UTF_8)
            return "$flags $tag \"$value\""
        }
    }
    // Unknown type (or a known type with malformed length): carry the
    // raw bytes as hex, as the core does — never drop the record.
    val hex = StringBuilder()
    for (i in start until end) hex.append("%02x".format(data[i].toInt() and 0xFF))
    return hex.toString()
}

private fun parseRrSection(
    data: ByteArray,
    firstOffset: Int,
    count: Int
): Pair<List<DnsRecord>, Int> {
    val records = ArrayList<DnsRecord>()
    var offset = firstOffset
    repeat(count) {
        val (name, afterName) = readName(data, offset)
        offset = afterName
        require(offset + 10 <= data.size) { "truncated record header" }
        val rtype = u16(data, offset)
        val ttl = u32(data, offset + 4)
        val rdlen = u16(data, offset + 8)
        val rdataStart = offset + 10
        val rdataEnd = rdataStart + rdlen
        require(rdataEnd <= data.size) { "truncated record data" }
        val value = parseRdata(data, rtype, rdataStart, rdlen)
        records.add(DnsRecord(name, TYPE_NAMES[rtype] ?: "TYPE$rtype", value, ttl))
        offset = rdataEnd
    }
    return Pair(records, offset)
}

/** Parse a DNS response packet. Throws IllegalArgumentException on malformed input. */
fun parseResponse(data: ByteArray): DnsMessage {
    require(data.size >= 12) { "packet shorter than DNS header" }
    val txid = u16(data, 0)
    val flags = u16(data, 2)
    val qdcount = u16(data, 4)
    val ancount = u16(data, 6)
    val nscount = u16(data, 8)
    val rcode = flags and 0x000F
    var offset = 12
    repeat(qdcount) {
        val (_, next) = readName(data, offset)
        offset = next
        require(offset + 4 <= data.size) { "truncated question section" }
        offset += 4
    }
    val (answers, afterAnswers) = parseRrSection(data, offset, ancount)
    val (authority, _) = parseRrSection(data, afterAnswers, nscount)
    return DnsMessage(txid, rcode, answers, authority)
}
