package com.shroudbyte.ui.screens

import android.webkit.CookieManager
import android.webkit.WebStorage
import android.webkit.WebView
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.shroudbyte.ShroudApplication

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(app: ShroudApplication, onBack: () -> Unit) {
    val current by remember { mutableStateOf(app.settings.load()) }
    var s by remember { mutableStateOf(current) }
    val ctx = LocalContext.current
    var clearConfirm by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Appearance", style = MaterialTheme.typography.titleMedium)
            ThemePicker(
                selected = s.theme,
                onSelect = { s = s.copy(theme = it).also(app.settings::save) },
            )

            HorizontalDivider()

            Text("Privacy", style = MaterialTheme.typography.titleMedium)
            ToggleRow("Block ads and trackers", s.enableAdblock) {
                s = s.copy(enableAdblock = it).also(app.settings::save)
            }
            ToggleRow("HTTPS-only mode", s.httpsOnly) {
                s = s.copy(httpsOnly = it).also(app.settings::save)
            }
            ToggleRow("Strip tracking parameters", s.stripTracking) {
                s = s.copy(stripTracking = it).also(app.settings::save)
            }
            ToggleRow("Send Do-Not-Track header", s.doNotTrack) {
                s = s.copy(doNotTrack = it).also(app.settings::save)
            }

            HorizontalDivider()

            Text("Browsing", style = MaterialTheme.typography.titleMedium)
            ToggleRow("Enable JavaScript", s.enableJavascript) {
                s = s.copy(enableJavascript = it).also(app.settings::save)
            }
            ToggleRow("Restore tabs on startup", s.restoreSession) {
                s = s.copy(restoreSession = it).also(app.settings::save)
            }

            HorizontalDivider()

            Text("Search engine", style = MaterialTheme.typography.titleMedium)
            SearchEnginePicker(
                current = s.searchEngine,
                onSelect = { s = s.copy(searchEngine = it).also(app.settings::save) },
            )

            HorizontalDivider()

            Text("Clear data", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { clearConfirm = "history" }) {
                    Text("History")
                }
                OutlinedButton(onClick = { clearConfirm = "cookies" }) {
                    Text("Cookies")
                }
                OutlinedButton(onClick = { clearConfirm = "cache" }) {
                    Text("Cache")
                }
            }

            Spacer(Modifier.height(32.dp))
        }
    }

    clearConfirm?.let { kind ->
        AlertDialog(
            onDismissRequest = { clearConfirm = null },
            title = { Text("Clear ${kind.replaceFirstChar { it.uppercase() }}?") },
            text = { Text("This cannot be undone.") },
            confirmButton = {
                TextButton(onClick = {
                    when (kind) {
                        "history" -> app.history.clear()
                        "cookies" -> CookieManager.getInstance().removeAllCookies(null)
                        "cache" -> {
                            // Per-WebView clearCache + storage flush.
                            WebView(ctx).clearCache(true)
                            WebStorage.getInstance().deleteAllData()
                        }
                    }
                    clearConfirm = null
                }) { Text("Clear") }
            },
            dismissButton = {
                TextButton(onClick = { clearConfirm = null }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun ToggleRow(label: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, modifier = Modifier.weight(1f))
        Switch(checked = value, onCheckedChange = onChange)
    }
}

@Composable
private fun ThemePicker(selected: String, onSelect: (String) -> Unit) {
    Column {
        for ((value, label) in listOf(
            "dark" to "Dark",
            "light" to "Light",
            "high_contrast" to "High contrast",
        )) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(
                    selected = selected == value,
                    onClick = { onSelect(value) },
                )
                Text(label)
            }
        }
    }
}

@Composable
private fun SearchEnginePicker(current: String, onSelect: (String) -> Unit) {
    val presets = listOf(
        "DuckDuckGo" to "https://duckduckgo.com/?q={q}",
        "Startpage"  to "https://www.startpage.com/sp/search?query={q}",
        "Brave"      to "https://search.brave.com/search?q={q}",
        "Mojeek"     to "https://www.mojeek.com/search?q={q}",
        "Google"     to "https://www.google.com/search?q={q}",
    )
    Column {
        for ((name, url) in presets) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(
                    selected = current == url,
                    onClick = { onSelect(url) },
                )
                Text(name)
            }
        }
    }
}
