package com.netscope.app

import android.graphics.Color

/**
 * NetScope design tokens for Android, dark theme.
 *
 * Values are taken from assets/branding/tokens.json, which is the
 * machine-readable form of docs/design/DESIGN_SYSTEM.md. If the
 * tokens change, this file is updated to match — it is a copy by
 * necessity (the app ships no JSON loader for its own theme), not a
 * second source of truth.
 */
object Tokens {
    val BACKGROUND: Int = Color.parseColor("#101419")
    val BACKGROUND_SECONDARY: Int = Color.parseColor("#151B22")
    val SURFACE: Int = Color.parseColor("#1B232C")
    val SURFACE_ELEVATED: Int = Color.parseColor("#222C37")
    val BORDER: Int = Color.parseColor("#303B47")
    val TEXT: Int = Color.parseColor("#EDF2F7")
    val TEXT_SECONDARY: Int = Color.parseColor("#9AA8B7")
    val TEXT_MUTED: Int = Color.parseColor("#687787")
    val ACCENT: Int = Color.parseColor("#3987D8")
    val ACCENT_SECONDARY: Int = Color.parseColor("#36A7B8")
    val SUCCESS: Int = Color.parseColor("#36A879")
    val WARNING: Int = Color.parseColor("#D69A42")
    val ERROR: Int = Color.parseColor("#D65B61")
    val ON_ACCENT: Int = Color.parseColor("#FFFFFF")

    /** Status colour for a verdict code; colour is never the only carrier. */
    fun verdictColor(code: String): Int = when (code) {
        VerdictCodes.OK -> SUCCESS
        VerdictCodes.SLOW_UNSTABLE -> WARNING
        VerdictCodes.UNKNOWN -> TEXT_SECONDARY
        else -> ERROR
    }
}
