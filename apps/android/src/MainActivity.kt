package com.netscope.app

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.res.ColorStateList
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import java.net.Inet4Address
import java.net.InetAddress
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.concurrent.thread

/**
 * NetScope for Android — a single activity with six sections
 * (Overview, Monitor, Diagnostics, Tools, History, Settings),
 * built from framework views and styled with the design tokens in
 * Tokens.kt (ADR-002: no AndroidX, no Compose in this build
 * environment). All diagnostics come from the probe modules in
 * this package, which port the Python core; nothing is uploaded
 * anywhere (ADR-006).
 */

private const val APP_VERSION = "0.4.0"

private const val SECTION_OVERVIEW = 0
private const val SECTION_MONITOR = 1
private const val SECTION_DIAGNOSTICS = 2
private const val SECTION_TOOLS = 3
private const val SECTION_HISTORY = 4
private const val SECTION_SETTINGS = 5

/** The brand reticle, drawn from the logo-symbol.svg geometry (48-unit grid). */
private class ReticleView(context: Context) : View(context) {
    private val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Tokens.ACCENT
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Tokens.ACCENT_SECONDARY
        style = Paint.Style.FILL
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val unit = minOf(width, height) / 48f
        strokePaint.strokeWidth = 3f * unit
        canvas.drawCircle(24f * unit, 24f * unit, 18f * unit, strokePaint)
        canvas.drawLine(24f * unit, 2f * unit, 24f * unit, 10f * unit, strokePaint)
        canvas.drawLine(24f * unit, 38f * unit, 24f * unit, 46f * unit, strokePaint)
        canvas.drawLine(2f * unit, 24f * unit, 10f * unit, 24f * unit, strokePaint)
        canvas.drawLine(38f * unit, 24f * unit, 46f * unit, 24f * unit, strokePaint)
        canvas.drawCircle(24f * unit, 24f * unit, 2.5f * unit, dotPaint)
    }
}

class MainActivity : Activity() {

    private var destroyed = false
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var prefs: SharedPreferences
    private lateinit var db: HistoryDb

    private lateinit var sectionHost: FrameLayout
    private val sections = arrayOfNulls<View>(6)
    private val navLabels = arrayOfNulls<TextView>(6)
    private var currentSection = -1

    // Diagnostics state
    private lateinit var diagHostInput: EditText
    private lateinit var diagRunButton: Button
    private lateinit var diagShareButton: Button
    private lateinit var diagProgress: ProgressBar
    private lateinit var diagOutput: TextView
    private var lastReportText: String? = null

    // Monitor state
    private lateinit var monitorHostInput: EditText
    private lateinit var monitorStartButton: Button
    private lateinit var monitorStopButton: Button
    private lateinit var monitorStats: TextView
    private lateinit var monitorChart: ChartView
    private val monitorSamples = ArrayList<Double?>()
    private var monitorRunning = false
    private var monitorTargetIp: String? = null
    private var monitorRunnable: Runnable? = null

    // History state
    private lateinit var historyList: ListView
    private var historyEntries: List<HistoryEntry> = emptyList()

    // ------------------------------------------------------------------
    // Small view factories (tokens applied in code)
    // ------------------------------------------------------------------

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun rounded(color: Int, borderColor: Int?, radiusDp: Int): GradientDrawable {
        val drawable = GradientDrawable()
        drawable.setColor(color)
        drawable.cornerRadius = dp(radiusDp).toFloat()
        if (borderColor != null) drawable.setStroke(dp(1), borderColor)
        return drawable
    }

    private fun text(
        value: String,
        sizeSp: Float = 14f,
        color: Int = Tokens.TEXT,
        bold: Boolean = false,
        mono: Boolean = false
    ): TextView {
        val view = TextView(this)
        view.text = value
        view.textSize = sizeSp
        view.setTextColor(color)
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD)
        if (mono) view.typeface = Typeface.MONOSPACE
        return view
    }

    private fun panel(): LinearLayout {
        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        layout.background = rounded(Tokens.SURFACE, Tokens.BORDER, 6)
        layout.setPadding(dp(16), dp(16), dp(16), dp(16))
        return layout
    }

    private fun primaryButton(label: String): Button {
        val button = Button(this)
        button.text = label
        button.isAllCaps = false
        button.textSize = 14f
        button.setTextColor(Tokens.ON_ACCENT)
        button.background = rounded(Tokens.ACCENT, null, 4)
        return button
    }

    private fun secondaryButton(label: String): Button {
        val button = Button(this)
        button.text = label
        button.isAllCaps = false
        button.textSize = 14f
        button.setTextColor(Tokens.TEXT)
        button.background = rounded(Tokens.SURFACE_ELEVATED, Tokens.BORDER, 4)
        return button
    }

    private fun input(hint: String, defaultValue: String = ""): EditText {
        val field = EditText(this)
        field.hint = hint
        field.setText(defaultValue)
        field.setTextColor(Tokens.TEXT)
        field.setHintTextColor(Tokens.TEXT_MUTED)
        field.textSize = 14f
        field.isSingleLine = true
        field.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI or
            InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
        field.background = rounded(Tokens.BACKGROUND_SECONDARY, Tokens.BORDER, 4)
        field.setPadding(dp(12), dp(10), dp(12), dp(10))
        return field
    }

    private fun numberInput(defaultValue: String): EditText {
        val field = input("", defaultValue)
        field.inputType = InputType.TYPE_CLASS_NUMBER
        return field
    }

    private fun darkSpinner(items: List<String>): Spinner {
        val spinner = Spinner(this)
        val adapter = object : ArrayAdapter<String>(
            this@MainActivity, android.R.layout.simple_spinner_item, items
        ) {
            override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                val view = super.getView(position, convertView, parent) as TextView
                view.setTextColor(Tokens.TEXT)
                view.setBackgroundColor(Tokens.SURFACE)
                return view
            }

            override fun getDropDownView(position: Int, convertView: View?, parent: ViewGroup): View {
                val view = super.getDropDownView(position, convertView, parent) as TextView
                view.setTextColor(Tokens.TEXT)
                view.setBackgroundColor(Tokens.SURFACE_ELEVATED)
                return view
            }
        }
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        spinner.adapter = adapter
        spinner.background = rounded(Tokens.BACKGROUND_SECONDARY, Tokens.BORDER, 4)
        return spinner
    }

    private fun progressBar(): ProgressBar {
        val bar = ProgressBar(this)
        bar.isIndeterminate = true
        bar.indeterminateTintList = ColorStateList.valueOf(Tokens.ACCENT)
        bar.visibility = View.GONE
        return bar
    }

    private fun outputView(initial: String): TextView {
        val view = text(initial, 12.5f, Tokens.TEXT_SECONDARY, mono = true)
        view.setTextIsSelectable(true)
        return view
    }

    private fun scrollOf(child: View): ScrollView {
        val scroll = ScrollView(this)
        scroll.addView(child)
        return scroll
    }

    private fun verticalLayout(): LinearLayout {
        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        layout.setPadding(dp(16), dp(16), dp(16), dp(16))
        return layout
    }

    private fun weighted(heightDp: Int): LinearLayout.LayoutParams {
        return if (heightDp < 0) {
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
            )
        } else {
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(heightDp)
            )
        }
    }

    private fun matchWrap(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        )

    private fun spaced(params: LinearLayout.LayoutParams, topDp: Int): LinearLayout.LayoutParams {
        params.topMargin = dp(topDp)
        return params
    }

    private fun infoRow(label: String, value: TextView): LinearLayout {
        val row = LinearLayout(this)
        row.orientation = LinearLayout.HORIZONTAL
        val labelView = text(label, 13f, Tokens.TEXT_SECONDARY)
        labelView.layoutParams = LinearLayout.LayoutParams(dp(110), LinearLayout.LayoutParams.WRAP_CONTENT)
        row.addView(labelView)
        row.addView(value)
        row.setPadding(0, dp(4), 0, dp(4))
        return row
    }

    // ------------------------------------------------------------------
    // Activity
    // ------------------------------------------------------------------

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("netscope_settings", Context.MODE_PRIVATE)
        db = HistoryDb(this)
        window.statusBarColor = Tokens.BACKGROUND

        val root = LinearLayout(this)
        root.orientation = LinearLayout.VERTICAL
        root.setBackgroundColor(Tokens.BACKGROUND)

        // Header: reticle mark + name + version.
        val header = LinearLayout(this)
        header.orientation = LinearLayout.HORIZONTAL
        header.gravity = Gravity.CENTER_VERTICAL
        header.setPadding(dp(16), dp(12), dp(16), dp(12))
        val mark = ReticleView(this)
        mark.layoutParams = LinearLayout.LayoutParams(dp(28), dp(28))
        header.addView(mark)
        val title = text("NetScope", 18f, Tokens.TEXT, bold = true)
        val titleParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
        )
        titleParams.leftMargin = dp(10)
        title.layoutParams = titleParams
        header.addView(title)
        val version = text(APP_VERSION, 12f, Tokens.TEXT_MUTED)
        val versionParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        version.layoutParams = versionParams
        version.gravity = Gravity.END
        header.addView(version)
        root.addView(header)

        sectionHost = FrameLayout(this)
        sectionHost.layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
        )
        root.addView(sectionHost)

        // Bottom navigation.
        val navDivider = View(this)
        navDivider.setBackgroundColor(Tokens.BORDER)
        navDivider.layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(1)
        )
        root.addView(navDivider)
        val nav = LinearLayout(this)
        nav.orientation = LinearLayout.HORIZONTAL
        nav.setBackgroundColor(Tokens.BACKGROUND_SECONDARY)
        val names = listOf("Overview", "Monitor", "Diagnostics", "Tools", "History", "Settings")
        for (index in names.indices) {
            val label = TextView(this)
            label.text = names[index]
            label.textSize = 10f
            label.gravity = Gravity.CENTER
            label.setPadding(dp(2), dp(12), dp(2), dp(12))
            label.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            label.setOnClickListener { showSection(index) }
            navLabels[index] = label
            nav.addView(label)
        }
        root.addView(nav)

        setContentView(root)

        sections[SECTION_OVERVIEW] = buildOverview()
        sections[SECTION_MONITOR] = buildMonitor()
        sections[SECTION_DIAGNOSTICS] = buildDiagnostics()
        sections[SECTION_TOOLS] = buildTools()
        sections[SECTION_HISTORY] = buildHistory()
        sections[SECTION_SETTINGS] = buildSettings()
        for (section in sections) {
            section!!.visibility = View.GONE
            section.layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
            sectionHost.addView(section)
        }
        showSection(SECTION_OVERVIEW)
    }

    override fun onDestroy() {
        destroyed = true
        monitorRunning = false
        monitorRunnable?.let { handler.removeCallbacks(it) }
        super.onDestroy()
    }

    private fun showSection(index: Int) {
        currentSection = index
        for (i in sections.indices) {
            sections[i]!!.visibility = if (i == index) View.VISIBLE else View.GONE
            val label = navLabels[i]!!
            if (i == index) {
                label.setTextColor(Tokens.ACCENT)
                label.setTypeface(Typeface.DEFAULT, Typeface.BOLD)
            } else {
                label.setTextColor(Tokens.TEXT_SECONDARY)
                label.setTypeface(Typeface.DEFAULT, Typeface.NORMAL)
            }
        }
        if (index == SECTION_OVERVIEW) refreshOverview()
        if (index == SECTION_HISTORY) refreshHistory()
    }

    private fun shareText(content: String) {
        val intent = Intent(Intent.ACTION_SEND)
        intent.type = "text/plain"
        intent.putExtra(Intent.EXTRA_TEXT, content)
        startActivity(Intent.createChooser(intent, "Share NetScope report"))
    }

    // ------------------------------------------------------------------
    // Overview
    // ------------------------------------------------------------------

    private lateinit var ovTransport: TextView
    private lateinit var ovInternet: TextView
    private lateinit var ovIp: TextView
    private lateinit var ovGateway: TextView
    private lateinit var ovDnsServers: TextView
    private lateinit var ovDnsCheck: TextView

    private fun buildOverview(): View {
        val layout = verticalLayout()
        layout.addView(text("Overview", 20f, Tokens.TEXT, bold = true))
        val panel = panel()
        panel.layoutParams = spaced(matchWrap(), 16)
        ovTransport = text("—", 13f, Tokens.TEXT, mono = true)
        ovInternet = text("—", 13f, Tokens.TEXT, mono = true)
        ovIp = text("—", 13f, Tokens.TEXT, mono = true)
        ovGateway = text("—", 13f, Tokens.TEXT, mono = true)
        ovDnsServers = text("—", 13f, Tokens.TEXT, mono = true)
        ovDnsCheck = text("—", 13f, Tokens.TEXT, mono = true)
        panel.addView(infoRow("Connection", ovTransport))
        panel.addView(infoRow("Internet", ovInternet))
        panel.addView(infoRow("Local IP", ovIp))
        panel.addView(infoRow("Gateway", ovGateway))
        panel.addView(infoRow("DNS servers", ovDnsServers))
        panel.addView(infoRow("DNS check", ovDnsCheck))
        layout.addView(panel)

        val run = primaryButton("Run diagnostics")
        run.layoutParams = spaced(matchWrap(), 16)
        run.setOnClickListener {
            showSection(SECTION_DIAGNOSTICS)
            startDiagnostics()
        }
        layout.addView(run)

        val refresh = secondaryButton("Refresh")
        refresh.layoutParams = spaced(matchWrap(), 8)
        refresh.setOnClickListener { refreshOverview() }
        layout.addView(refresh)

        val note = text(
            "Connection details come from the system network APIs. " +
                "The DNS check resolves example.com with the system resolver.",
            12f, Tokens.TEXT_MUTED
        )
        note.layoutParams = spaced(matchWrap(), 16)
        layout.addView(note)
        return layout
    }

    private fun refreshOverview() {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork
        if (network == null) {
            ovTransport.text = "No active network"
            ovInternet.text = "—"
            ovIp.text = "—"
            ovGateway.text = "—"
            ovDnsServers.text = "—"
        } else {
            val caps = cm.getNetworkCapabilities(network)
            ovTransport.text = when {
                caps == null -> "Unknown"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "Wi-Fi"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "Cellular"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "Ethernet"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) -> "VPN"
                else -> "Other"
            }
            ovInternet.text = when {
                caps == null -> "Unknown"
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) ->
                    "Validated — internet reachable"
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) ->
                    "Connected, not validated — a captive portal or an outage is possible"
                else -> "No internet capability reported"
            }
            val props = cm.getLinkProperties(network)
            val addresses = props?.linkAddresses?.mapNotNull { it.address?.hostAddress } ?: emptyList()
            ovIp.text = addresses.firstOrNull { address ->
                try {
                    InetAddress.getByName(address) is Inet4Address
                } catch (exc: Exception) {
                    false
                }
            } ?: addresses.firstOrNull() ?: "not reported"
            val gateway = props?.routes?.firstOrNull { route ->
                route.destination.prefixLength == 0 && route.gateway != null
            }?.gateway?.hostAddress
            ovGateway.text = gateway ?: "not reported"
            val dns = props?.dnsServers?.mapNotNull { it.hostAddress } ?: emptyList()
            ovDnsServers.text = if (dns.isEmpty()) "not reported" else dns.joinToString(", ")
        }
        ovDnsCheck.text = "resolving…"
        thread {
            val (addresses, error, latencyMs) = systemResolveTimed("example.com")
            if (destroyed) return@thread
            runOnUiThread {
                if (destroyed) return@runOnUiThread
                ovDnsCheck.text = if (addresses.isNotEmpty()) {
                    "${addresses.first()} (${String.format(Locale.US, "%.0f ms", latencyMs)})"
                } else {
                    "failed (${error ?: "no answer"})"
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Diagnostics
    // ------------------------------------------------------------------

    private fun buildDiagnostics(): View {
        val layout = verticalLayout()
        layout.addView(text("Diagnostics", 20f, Tokens.TEXT, bold = true))
        diagHostInput = input("Host or URL", "example.com")
        diagHostInput.layoutParams = spaced(matchWrap(), 16)
        layout.addView(diagHostInput)
        diagRunButton = primaryButton("Run check")
        diagRunButton.layoutParams = spaced(matchWrap(), 8)
        diagRunButton.setOnClickListener { startDiagnostics() }
        layout.addView(diagRunButton)
        diagProgress = progressBar()
        diagProgress.layoutParams = spaced(matchWrap(), 8)
        layout.addView(diagProgress)
        diagOutput = outputView("No check run yet.")
        val scroll = scrollOf(diagOutput)
        scroll.layoutParams = spaced(weighted(-1), 12)
        layout.addView(scroll)
        diagShareButton = secondaryButton("Share report")
        diagShareButton.isEnabled = false
        diagShareButton.layoutParams = spaced(matchWrap(), 8)
        diagShareButton.setOnClickListener {
            lastReportText?.let { report -> shareText(report) }
        }
        layout.addView(diagShareButton)
        return layout
    }

    private fun startDiagnostics() {
        val raw = diagHostInput.text.toString()
        val host = try {
            parseTarget(raw)
        } catch (exc: IllegalArgumentException) {
            diagOutput.text = exc.message ?: "Invalid host"
            return
        }
        diagRunButton.isEnabled = false
        diagProgress.visibility = View.VISIBLE
        diagOutput.text = "Running checks for $host…"
        thread {
            val report = runChecks(host)
            val reportText = formatReport(report)
            if (destroyed) return@thread
            db.insert(
                System.currentTimeMillis(), report.host, report.verdict.code,
                report.tcp[443]?.avgLatencyMs, reportText
            )
            runOnUiThread {
                if (destroyed) return@runOnUiThread
                lastReportText = reportText
                diagOutput.text = reportText
                diagShareButton.isEnabled = true
                diagRunButton.isEnabled = true
                diagProgress.visibility = View.GONE
            }
        }
    }

    // ------------------------------------------------------------------
    // Monitor
    // ------------------------------------------------------------------

    private fun buildMonitor(): View {
        val layout = verticalLayout()
        layout.addView(text("Monitor", 20f, Tokens.TEXT, bold = true))
        val hint = text(
            "Repeated TCP connects to port 443. The interval comes from Settings.",
            12f, Tokens.TEXT_MUTED
        )
        hint.layoutParams = spaced(matchWrap(), 8)
        layout.addView(hint)
        monitorHostInput = input("Host", "example.com")
        monitorHostInput.layoutParams = spaced(matchWrap(), 12)
        layout.addView(monitorHostInput)
        val buttons = LinearLayout(this)
        buttons.orientation = LinearLayout.HORIZONTAL
        monitorStartButton = primaryButton("Start")
        monitorStartButton.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        monitorStopButton = secondaryButton("Stop")
        val stopParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        stopParams.leftMargin = dp(8)
        monitorStopButton.layoutParams = stopParams
        monitorStopButton.isEnabled = false
        monitorStartButton.setOnClickListener { startMonitor() }
        monitorStopButton.setOnClickListener { stopMonitor() }
        buttons.addView(monitorStartButton)
        buttons.addView(monitorStopButton)
        buttons.layoutParams = spaced(matchWrap(), 8)
        layout.addView(buttons)
        monitorChart = ChartView(this)
        monitorChart.setBackgroundColor(Tokens.SURFACE)
        monitorChart.layoutParams = spaced(weighted(170), 12)
        layout.addView(monitorChart)
        monitorStats = text("No samples yet.", 12.5f, Tokens.TEXT_SECONDARY, mono = true)
        monitorStats.layoutParams = spaced(matchWrap(), 12)
        layout.addView(monitorStats)
        return layout
    }

    private fun startMonitor() {
        val host = try {
            parseTarget(monitorHostInput.text.toString())
        } catch (exc: IllegalArgumentException) {
            monitorStats.text = exc.message ?: "Invalid host"
            return
        }
        monitorSamples.clear()
        monitorChart.setSamples(emptyList())
        monitorRunning = true
        monitorStartButton.isEnabled = false
        monitorStopButton.isEnabled = true
        monitorStats.text = "Resolving $host…"
        thread {
            val ip = try {
                InetAddress.getAllByName(host).firstOrNull { it.address.size == 4 }?.hostAddress
            } catch (exc: Exception) {
                null
            }
            if (destroyed) return@thread
            runOnUiThread {
                if (destroyed) return@runOnUiThread
                if (ip == null) {
                    monitorStats.text = "Could not resolve $host to an IPv4 address."
                    stopMonitor()
                } else {
                    monitorTargetIp = ip
                    monitorStats.text = "Monitoring $host ($ip), port 443…"
                    scheduleMonitorTick(0)
                }
            }
        }
    }

    private fun scheduleMonitorTick(delayMs: Long) {
        if (!monitorRunning) return
        val runnable = Runnable {
            if (!monitorRunning || destroyed) return@Runnable
            val ip = monitorTargetIp ?: return@Runnable
            thread {
                val sample = tcpConnectOnce(ip, 443, 1500)
                if (destroyed) return@thread
                runOnUiThread {
                    if (destroyed || !monitorRunning) return@runOnUiThread
                    monitorSamples.add(sample)
                    while (monitorSamples.size > 120) monitorSamples.removeAt(0)
                    monitorChart.setSamples(ArrayList(monitorSamples))
                    updateMonitorStats()
                    val intervalSec = prefs.getInt("monitor_interval_s", 2).coerceIn(1, 60)
                    scheduleMonitorTick(intervalSec * 1000L)
                }
            }
        }
        monitorRunnable = runnable
        handler.postDelayed(runnable, delayMs)
    }

    private fun updateMonitorStats() {
        val ok = monitorSamples.filterNotNull()
        val loss = packetLoss(monitorSamples.size, ok.size, monitorSamples.size - ok.size)
        val stats = latencyStats(ok)
        fun fmt(value: Double?): String =
            if (value != null) String.format(Locale.US, "%.0f", value) else "—"
        monitorStats.text =
            "last ${fmt(ok.lastOrNull())} ms · avg ${fmt(stats.avg)} · min ${fmt(stats.min)} · " +
                "max ${fmt(stats.max)} · p95 ${fmt(stats.p95)} · jitter ${fmt(stats.jitterAvg)} ms · " +
                "loss ${fmt(loss.lossPercent)}% (${ok.size}/${monitorSamples.size})"
    }

    private fun stopMonitor() {
        monitorRunning = false
        monitorRunnable?.let { handler.removeCallbacks(it) }
        monitorStartButton.isEnabled = true
        monitorStopButton.isEnabled = false
    }

    // ------------------------------------------------------------------
    // Tools
    // ------------------------------------------------------------------

    private fun buildTools(): View {
        val layout = verticalLayout()
        layout.addView(text("Tools", 20f, Tokens.TEXT, bold = true))
        val switcher = LinearLayout(this)
        switcher.orientation = LinearLayout.HORIZONTAL
        switcher.layoutParams = spaced(matchWrap(), 12)
        val host = FrameLayout(this)
        host.layoutParams = spaced(weighted(-1), 12)
        val panels = listOf(buildDnsTool(), buildLatencyTool(), buildRouteTool(), buildTlsTool())
        val names = listOf("DNS", "Latency", "Route", "TLS")
        val buttons = ArrayList<Button>()
        for (index in panels.indices) {
            val button = secondaryButton(names[index])
            val params = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            if (index > 0) params.leftMargin = dp(8)
            button.layoutParams = params
            button.setOnClickListener {
                for (i in panels.indices) {
                    panels[i].visibility = if (i == index) View.VISIBLE else View.GONE
                    buttons[i].setTextColor(if (i == index) Tokens.ACCENT else Tokens.TEXT)
                }
            }
            buttons.add(button)
            switcher.addView(button)
            panels[index].visibility = if (index == 0) View.VISIBLE else View.GONE
            panels[index].layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
            host.addView(panels[index])
        }
        buttons[0].setTextColor(Tokens.ACCENT)
        layout.addView(switcher)
        layout.addView(host)
        return layout
    }

    private fun toolPanel(): LinearLayout {
        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        return layout
    }

    private fun buildDnsTool(): View {
        val layout = toolPanel()
        val nameInput = input("Name, e.g. example.com (IP for PTR)", "")
        layout.addView(nameInput)
        val typeSpinner = darkSpinner(listOf("A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR"))
        typeSpinner.layoutParams = spaced(matchWrap(), 8)
        layout.addView(typeSpinner)
        val resolverSpinner = darkSpinner(DEFAULT_RESOLVERS)
        val savedResolver = prefs.getString("resolver", "1.1.1.1") ?: "1.1.1.1"
        val savedIndex = DEFAULT_RESOLVERS.indexOf(savedResolver)
        if (savedIndex >= 0) resolverSpinner.setSelection(savedIndex)
        resolverSpinner.layoutParams = spaced(matchWrap(), 8)
        layout.addView(resolverSpinner)
        val output = outputView("No lookup run yet.")
        val progress = progressBar()
        val run = primaryButton("Look up")
        run.layoutParams = spaced(matchWrap(), 8)
        run.setOnClickListener {
            val rawName = nameInput.text.toString().trim().trimEnd('.').lowercase()
            val typeName = typeSpinner.selectedItem as String
            val resolver = resolverSpinner.selectedItem as String
            if (rawName.isEmpty()) {
                output.text = "Enter a name to look up."
                return@setOnClickListener
            }
            val qtype = qtypeForName(typeName) ?: QTYPE_A
            val queryName = if (typeName == "PTR") {
                reverseNameForIpv4(rawName) ?: rawName
            } else {
                rawName
            }
            run.isEnabled = false
            progress.visibility = View.VISIBLE
            output.text = "Querying $resolver for $queryName $typeName…"
            thread {
                val outcome = lookupRecords(resolver, queryName, qtype)
                if (destroyed) return@thread
                runOnUiThread {
                    if (destroyed) return@runOnUiThread
                    run.isEnabled = true
                    progress.visibility = View.GONE
                    output.text = formatDnsOutcome(outcome)
                }
            }
        }
        layout.addView(run)
        progress.layoutParams = spaced(matchWrap(), 8)
        layout.addView(progress)
        val scroll = scrollOf(output)
        scroll.layoutParams = spaced(weighted(-1), 12)
        layout.addView(scroll)
        return layout
    }

    private fun formatDnsOutcome(outcome: DnsLookupOutcome): String {
        val out = StringBuilder()
        val latency = if (outcome.latencyMs != null) {
            String.format(Locale.US, "%.0f ms", outcome.latencyMs)
        } else {
            "no answer"
        }
        out.appendLine("${outcome.qname} ${outcome.qtypeName} via ${outcome.resolver}: ${outcome.status} ($latency)")
        if (outcome.error != null) out.appendLine("error: ${outcome.error}")
        for (record in outcome.records) {
            out.appendLine("${record.name}  ${record.type}  ${record.ttl}  ${record.value}")
        }
        for (record in outcome.authority) {
            out.appendLine("authority: ${record.name}  ${record.type}  ${record.ttl}  ${record.value}")
        }
        if (outcome.records.isEmpty() && outcome.status == "ok") {
            out.appendLine("(no records of this type in the answer)")
        }
        return out.toString().trimEnd()
    }

    private fun buildLatencyTool(): View {
        val layout = toolPanel()
        val hostInput = input("Host", "example.com")
        layout.addView(hostInput)
        val countInput = numberInput(prefs.getInt("latency_count", 10).toString())
        countInput.hint = "Samples"
        countInput.layoutParams = spaced(matchWrap(), 8)
        layout.addView(countInput)
        val progressLabel = text("", 12f, Tokens.TEXT_MUTED)
        layout.addView(progressLabel)
        val output = outputView("No latency test run yet.")
        val run = primaryButton("Run latency test")
        run.layoutParams = spaced(matchWrap(), 8)
        run.setOnClickListener {
            val host = try {
                parseTarget(hostInput.text.toString())
            } catch (exc: IllegalArgumentException) {
                output.text = exc.message ?: "Invalid host"
                return@setOnClickListener
            }
            val count = countInput.text.toString().toIntOrNull()?.coerceIn(1, 200) ?: 10
            run.isEnabled = false
            output.text = "Measuring TCP connect latency to $host:443…"
            thread {
                val samples = ArrayList<Double?>()
                for (i in 1..count) {
                    samples.add(tcpConnectOnce(host, 443, 2000))
                    if (destroyed) return@thread
                    runOnUiThread {
                        if (!destroyed) progressLabel.text = "Sample $i of $count"
                    }
                }
                val ok = samples.filterNotNull()
                val loss = packetLoss(samples.size, ok.size, samples.size - ok.size)
                val stats = latencyStats(ok)
                fun fmt(value: Double?): String =
                    if (value != null) String.format(Locale.US, "%.1f ms", value) else "—"
                val text = StringBuilder()
                text.appendLine("Target: $host:443")
                text.appendLine(
                    "Samples: ${samples.size} sent, ${ok.size} received, " +
                        "${String.format(Locale.US, "%.0f", loss.lossPercent)}% loss"
                )
                text.appendLine("min ${fmt(stats.min)} · avg ${fmt(stats.avg)} · median ${fmt(stats.median)}")
                text.appendLine("p95 ${fmt(stats.p95)} · max ${fmt(stats.max)} · stddev ${fmt(stats.stddev)}")
                text.appendLine("jitter avg ${fmt(stats.jitterAvg)} · max ${fmt(stats.jitterMax)}")
                if (destroyed) return@thread
                runOnUiThread {
                    if (destroyed) return@runOnUiThread
                    progressLabel.text = ""
                    output.text = text.toString().trimEnd()
                    run.isEnabled = true
                }
            }
        }
        layout.addView(run)
        val scroll = scrollOf(output)
        scroll.layoutParams = spaced(weighted(-1), 12)
        layout.addView(scroll)
        return layout
    }

    private fun buildRouteTool(): View {
        val layout = toolPanel()
        val hostInput = input("Host", "example.com")
        layout.addView(hostInput)
        val output = outputView(
            "No route traced yet.\n\nAndroid apps cannot read ICMP replies, so this is the " +
                "TCP fallback: TTL-limited connects. It shows how far connects get, " +
                "not the addresses of intermediate routers."
        )
        val progress = progressBar()
        val run = primaryButton("Trace route")
        run.layoutParams = spaced(matchWrap(), 8)
        run.setOnClickListener {
            val host = try {
                parseTarget(hostInput.text.toString())
            } catch (exc: IllegalArgumentException) {
                output.text = exc.message ?: "Invalid host"
                return@setOnClickListener
            }
            run.isEnabled = false
            progress.visibility = View.VISIBLE
            output.text = "Tracing route to $host (this can take up to a minute)…"
            thread {
                val result = probeRouteAndroid(host)
                if (destroyed) return@thread
                runOnUiThread {
                    if (destroyed) return@runOnUiThread
                    run.isEnabled = true
                    progress.visibility = View.GONE
                    output.text = formatRoute(result)
                }
            }
        }
        layout.addView(run)
        progress.layoutParams = spaced(matchWrap(), 8)
        layout.addView(progress)
        val scroll = scrollOf(output)
        scroll.layoutParams = spaced(weighted(-1), 12)
        layout.addView(scroll)
        return layout
    }

    private fun formatRoute(result: RouteResult): String {
        val out = StringBuilder()
        out.appendLine("Target: ${result.host} (${result.destinationIp ?: "unresolved"})")
        out.appendLine("Method: TCP connect probes with limited TTL")
        out.appendLine()
        if (result.error != null) {
            out.appendLine("Error: ${result.error}")
        }
        for (hop in result.hops) {
            val value = if (hop.responded) {
                "${hop.ip}  ${String.format(Locale.US, "%.0f ms", hop.rttMs ?: 0.0)}"
            } else {
                "*  (no answer)"
            }
            out.appendLine("  " + hop.ttl.toString().padEnd(4) + value)
        }
        out.appendLine()
        out.appendLine("Stops: ${result.stopPoint}")
        out.appendLine(result.note)
        return out.toString().trimEnd()
    }

    private fun buildTlsTool(): View {
        val layout = toolPanel()
        val hostInput = input("Host", "example.com")
        layout.addView(hostInput)
        val output = outputView("No certificate inspected yet.")
        val progress = progressBar()
        val run = primaryButton("Inspect certificate")
        run.layoutParams = spaced(matchWrap(), 8)
        run.setOnClickListener {
            val host = try {
                parseTarget(hostInput.text.toString())
            } catch (exc: IllegalArgumentException) {
                output.text = exc.message ?: "Invalid host"
                return@setOnClickListener
            }
            run.isEnabled = false
            progress.visibility = View.VISIBLE
            output.text = "Connecting to $host:443…"
            thread {
                val info = inspectTls(host)
                if (destroyed) return@thread
                runOnUiThread {
                    if (destroyed) return@runOnUiThread
                    run.isEnabled = true
                    progress.visibility = View.GONE
                    output.text = formatTlsInfo(info)
                }
            }
        }
        layout.addView(run)
        progress.layoutParams = spaced(matchWrap(), 8)
        layout.addView(progress)
        val scroll = scrollOf(output)
        scroll.layoutParams = spaced(weighted(-1), 12)
        layout.addView(scroll)
        return layout
    }

    private fun formatTlsInfo(info: TlsInfo): String {
        if (!info.ok) {
            return "TLS inspection failed for ${info.hostname} (${info.errorKind}): ${info.error}"
        }
        val out = StringBuilder()
        out.appendLine("Host: ${info.hostname}")
        out.appendLine("Protocol: ${info.protocol}")
        out.appendLine("Cipher: ${info.cipherSuite}")
        out.appendLine("Subject: ${info.subject}")
        out.appendLine("Issuer: ${info.issuer}")
        out.appendLine("Valid from: ${info.notBefore}")
        out.appendLine("Valid until: ${info.notAfter}")
        val days = info.daysRemaining
        if (days != null) {
            out.appendLine(
                if (days >= 0) "Days remaining: $days" else "Expired ${-days} day(s) ago"
            )
        }
        return out.toString().trimEnd()
    }

    // ------------------------------------------------------------------
    // History
    // ------------------------------------------------------------------

    private fun buildHistory(): View {
        val layout = verticalLayout()
        layout.addView(text("History", 20f, Tokens.TEXT, bold = true))
        val hint = text(
            "Stored on this device only. Tap a run to read or share its report.",
            12f, Tokens.TEXT_MUTED
        )
        hint.layoutParams = spaced(matchWrap(), 8)
        layout.addView(hint)
        historyList = ListView(this)
        historyList.layoutParams = spaced(weighted(-1), 12)
        historyList.setBackgroundColor(Tokens.SURFACE)
        historyList.setOnItemClickListener { _, _, position, _ ->
            showHistoryEntry(historyEntries[position])
        }
        layout.addView(historyList)
        val clear = secondaryButton("Clear all history")
        clear.layoutParams = spaced(matchWrap(), 8)
        clear.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Clear history")
                .setMessage("Delete every stored diagnostics run?")
                .setPositiveButton("Delete") { _, _ ->
                    db.clear()
                    refreshHistory()
                }
                .setNegativeButton("Cancel", null)
                .show()
        }
        layout.addView(clear)
        return layout
    }

    private fun refreshHistory() {
        historyEntries = db.list()
        val format = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US)
        val labels = historyEntries.map { entry ->
            val avg = entry.avgLatencyMs?.let {
                String.format(Locale.US, " · avg %.0f ms", it)
            } ?: ""
            "${entry.host} — ${entry.verdict} — ${format.format(Date(entry.timestampMs))}$avg"
        }
        val adapter = object : ArrayAdapter<String>(
            this, android.R.layout.simple_list_item_1, labels
        ) {
            override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                val view = super.getView(position, convertView, parent) as TextView
                view.setTextColor(Tokens.TEXT)
                view.textSize = 13f
                return view
            }
        }
        historyList.adapter = adapter
    }

    private fun showHistoryEntry(entry: HistoryEntry) {
        val report = db.report(entry.id) ?: "(report no longer stored)"
        val textView = TextView(this)
        textView.text = report
        textView.textSize = 12f
        textView.typeface = Typeface.MONOSPACE
        textView.setTextColor(Tokens.TEXT)
        textView.setPadding(dp(16), dp(16), dp(16), dp(16))
        val scroll = ScrollView(this)
        scroll.addView(textView)
        AlertDialog.Builder(this)
            .setTitle(entry.host)
            .setView(scroll)
            .setPositiveButton("Close", null)
            .setNeutralButton("Share") { _, _ -> shareText(report) }
            .setNegativeButton("Delete") { _, _ ->
                db.delete(entry.id)
                refreshHistory()
            }
            .show()
    }

    // ------------------------------------------------------------------
    // Settings
    // ------------------------------------------------------------------

    private fun buildSettings(): View {
        val layout = verticalLayout()
        layout.addView(text("Settings", 20f, Tokens.TEXT, bold = true))

        val resolverLabel = text("Default resolver (DNS tool)", 13f, Tokens.TEXT_SECONDARY)
        resolverLabel.layoutParams = spaced(matchWrap(), 16)
        layout.addView(resolverLabel)
        val resolverSpinner = darkSpinner(DEFAULT_RESOLVERS)
        val savedResolver = prefs.getString("resolver", "1.1.1.1") ?: "1.1.1.1"
        val savedIndex = DEFAULT_RESOLVERS.indexOf(savedResolver)
        if (savedIndex >= 0) resolverSpinner.setSelection(savedIndex)
        resolverSpinner.layoutParams = spaced(matchWrap(), 8)
        layout.addView(resolverSpinner)

        val intervalLabel = text("Monitor interval, seconds (1–60)", 13f, Tokens.TEXT_SECONDARY)
        intervalLabel.layoutParams = spaced(matchWrap(), 16)
        layout.addView(intervalLabel)
        val intervalInput = numberInput(prefs.getInt("monitor_interval_s", 2).toString())
        intervalInput.layoutParams = spaced(matchWrap(), 8)
        layout.addView(intervalInput)

        val countLabel = text("Latency test samples (3–100)", 13f, Tokens.TEXT_SECONDARY)
        countLabel.layoutParams = spaced(matchWrap(), 16)
        layout.addView(countLabel)
        val countInput = numberInput(prefs.getInt("latency_count", 10).toString())
        countInput.layoutParams = spaced(matchWrap(), 8)
        layout.addView(countInput)

        val save = primaryButton("Save settings")
        save.layoutParams = spaced(matchWrap(), 16)
        save.setOnClickListener {
            val interval = intervalInput.text.toString().toIntOrNull()?.coerceIn(1, 60) ?: 2
            val count = countInput.text.toString().toIntOrNull()?.coerceIn(3, 100) ?: 10
            prefs.edit()
                .putString("resolver", resolverSpinner.selectedItem as String)
                .putInt("monitor_interval_s", interval)
                .putInt("latency_count", count)
                .apply()
            intervalInput.setText(interval.toString())
            countInput.setText(count.toString())
            Toast.makeText(this, "Settings saved", Toast.LENGTH_SHORT).show()
        }
        layout.addView(save)

        val about = text(
            "NetScope $APP_VERSION for Android. Framework build (ADR-002): no " +
                "AndroidX, no Compose. Diagnostics run on this device against the " +
                "resolvers shown; no telemetry, no uploads (ADR-006). History is " +
                "stored only in the app's local database.",
            12f, Tokens.TEXT_MUTED
        )
        about.layoutParams = spaced(matchWrap(), 24)
        layout.addView(about)
        return layout
    }
}
