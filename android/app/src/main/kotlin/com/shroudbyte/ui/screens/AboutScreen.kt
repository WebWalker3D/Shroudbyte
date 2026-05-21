package com.shroudbyte.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.shroudbyte.BuildConfig
import com.shroudbyte.CrashLogger
import com.shroudbyte.ShroudApplication

/**
 * Local About + crash log viewer. Mirrors `shroud://about` and
 * `shroud://crashes` on desktop, combined into one scrolling page.
 * Crash data lives in the app's private files dir and is never uploaded;
 * the user can copy excerpts to the clipboard manually.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutScreen(app: ShroudApplication, onBack: () -> Unit) {
    val ctx = LocalContext.current
    val log = remember { CrashLogger.crashLogFile(app.storage) }
    val logText = remember { if (log.exists()) log.readText() else "" }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("About") },
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
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Shroudbyte", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Version ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.outline,
            )
            Text(
                "Privacy-focused browser. " +
                "Shroudbyte never uploads usage data or crash reports. " +
                "Crash details live in this device's private storage " +
                "and are only visible to you.",
                style = MaterialTheme.typography.bodyMedium,
            )

            HorizontalDivider()

            Text("Crash log", style = MaterialTheme.typography.titleMedium)
            if (logText.isBlank()) {
                Text(
                    "No crashes recorded.",
                    color = MaterialTheme.colorScheme.outline,
                )
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { copy(ctx, logText) }) {
                        Text("Copy to clipboard")
                    }
                    OutlinedButton(onClick = {
                        log.delete()
                    }) { Text("Delete") }
                }
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = MaterialTheme.shapes.medium,
                ) {
                    Text(
                        text = logText.takeLast(8000),  // cap displayed bytes
                        modifier = Modifier
                            .padding(12.dp)
                            .fillMaxWidth(),
                        fontFamily = FontFamily.Monospace,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}

private fun copy(ctx: Context, text: String) {
    val cm = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("Shroudbyte crash log", text))
}
