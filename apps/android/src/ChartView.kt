package com.netscope.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.view.View

/**
 * Latency line chart drawn directly on the canvas: the most recent
 * samples in order, failures shown as gaps with a marker on the
 * baseline. Colours come from the design tokens. The chart is a
 * drawing of measured data only — no smoothing, no animation.
 */
class ChartView(context: Context) : View(context) {

    private var samples: List<Double?> = emptyList()

    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Tokens.BORDER
        strokeWidth = 1f
    }
    private val linePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Tokens.ACCENT
        strokeWidth = 2.5f
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val failPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Tokens.ERROR
        strokeWidth = 2f
    }
    private val axisPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Tokens.TEXT_MUTED
        textSize = 26f
    }

    fun setSamples(newSamples: List<Double?>) {
        samples = newSamples
        contentDescription = describe(samples)
        invalidate()
    }

    private fun describe(data: List<Double?>): String {
        val ok = data.filterNotNull()
        if (ok.isEmpty()) return "Latency chart, no successful samples yet"
        return "Latency chart, ${data.size} samples, latest ${ok.last().toInt()} milliseconds"
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val width = width.toFloat()
        val height = height.toFloat()
        if (width == 0f || height == 0f) return

        val leftPad = 64f
        val bottomPad = 8f
        val topPad = 10f
        val plotW = width - leftPad - 8f
        val plotH = height - topPad - bottomPad
        val baseline = topPad + plotH

        val values = samples.filterNotNull()
        val maxValue = maxOf(50.0, (values.maxOrNull() ?: 50.0) * 1.2)

        // Horizontal gridlines at 0, 1/2 and full scale, with labels.
        for (fraction in listOf(0.0, 0.5, 1.0)) {
            val y = baseline - (fraction * plotH).toFloat()
            canvas.drawLine(leftPad, y, leftPad + plotW, y, gridPaint)
            val label = (fraction * maxValue).toInt().toString()
            canvas.drawText(label, 8f, y + 9f, axisPaint)
        }

        if (samples.size < 2) return
        val stepX = plotW / (samples.size - 1)
        var previous: Pair<Float, Float>? = null
        samples.forEachIndexed { index, sample ->
            val x = leftPad + index * stepX
            if (sample == null) {
                // Failure: break the line, mark the baseline.
                canvas.drawLine(x - 4f, baseline - 4f, x + 4f, baseline + 4f, failPaint)
                canvas.drawLine(x - 4f, baseline + 4f, x + 4f, baseline - 4f, failPaint)
                previous = null
            } else {
                val y = baseline - (sample / maxValue * plotH).toFloat()
                val point = Pair(x, y)
                val prev = previous
                if (prev != null) canvas.drawLine(prev.first, prev.second, point.first, point.second, linePaint)
                previous = point
            }
        }
    }
}
