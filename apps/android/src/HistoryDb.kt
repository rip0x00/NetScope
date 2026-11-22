package com.netscope.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/**
 * Local history storage (framework SQLite, per ADR-002 and
 * ADR-005). Every diagnostics run is stored with its full text
 * report so it can be re-read and shared later. Data never leaves
 * the device (ADR-006).
 */

data class HistoryEntry(
    val id: Long,
    val timestampMs: Long,
    val host: String,
    val verdict: String,
    val avgLatencyMs: Double?
)

class HistoryDb(context: Context) :
    SQLiteOpenHelper(context.applicationContext, DATABASE_NAME, null, DATABASE_VERSION) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE $TABLE_RUNS (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "ts INTEGER NOT NULL, " +
                "host TEXT NOT NULL, " +
                "verdict TEXT NOT NULL, " +
                "avg_latency_ms REAL, " +
                "report TEXT NOT NULL)"
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // Version 1 is the first schema; nothing to migrate yet.
    }

    fun insert(timestampMs: Long, host: String, verdict: String, avgLatencyMs: Double?, report: String) {
        val values = ContentValues().apply {
            put("ts", timestampMs)
            put("host", host)
            put("verdict", verdict)
            if (avgLatencyMs != null) put("avg_latency_ms", avgLatencyMs) else putNull("avg_latency_ms")
            put("report", report)
        }
        writableDatabase.insert(TABLE_RUNS, null, values)
    }

    /** Most recent runs first, without the report text. */
    fun list(limit: Int = 200): List<HistoryEntry> {
        val entries = ArrayList<HistoryEntry>()
        val cursor = readableDatabase.query(
            TABLE_RUNS,
            arrayOf("id", "ts", "host", "verdict", "avg_latency_ms"),
            null, null, null, null,
            "ts DESC",
            limit.toString()
        )
        cursor.use {
            while (it.moveToNext()) {
                entries.add(
                    HistoryEntry(
                        id = it.getLong(0),
                        timestampMs = it.getLong(1),
                        host = it.getString(2),
                        verdict = it.getString(3),
                        avgLatencyMs = if (it.isNull(4)) null else it.getDouble(4)
                    )
                )
            }
        }
        return entries
    }

    /** The stored text report for one run, or null if it is gone. */
    fun report(id: Long): String? {
        val cursor = readableDatabase.query(
            TABLE_RUNS, arrayOf("report"), "id = ?", arrayOf(id.toString()),
            null, null, null
        )
        cursor.use {
            return if (it.moveToFirst()) it.getString(0) else null
        }
    }

    fun delete(id: Long) {
        writableDatabase.delete(TABLE_RUNS, "id = ?", arrayOf(id.toString()))
    }

    fun clear() {
        writableDatabase.delete(TABLE_RUNS, null, null)
    }

    companion object {
        private const val DATABASE_NAME = "netscope_history.db"
        private const val DATABASE_VERSION = 1
        private const val TABLE_RUNS = "runs"
    }
}
