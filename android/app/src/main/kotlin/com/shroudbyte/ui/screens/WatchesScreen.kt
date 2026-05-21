package com.shroudbyte.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.shroudbyte.ShroudApplication
import com.shroudbyte.watches.PageWatch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WatchesScreen(
    app: ShroudApplication,
    onBack: () -> Unit,
    onOpen: (String) -> Unit,
) {
    var entries by remember { mutableStateOf(app.watches.all()) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Page watches (${entries.size})") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        if (entries.isEmpty()) {
            Box(modifier = Modifier.padding(padding).fillMaxSize(),
                contentAlignment = Alignment.Center) {
                Text(
                    "No watches yet — add one from the drawer while a page is open.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.padding(32.dp),
                )
            }
            return@Scaffold
        }
        LazyColumn(modifier = Modifier.padding(padding).fillMaxSize()) {
            items(entries, key = { it.id }) { w ->
                WatchRow(
                    watch = w,
                    onOpen = { onOpen(w.url) },
                    onDelete = {
                        app.watches.remove(w.id)
                        entries = app.watches.all()
                    },
                    onIntervalChange = { mins ->
                        app.watches.setInterval(w.id, mins)
                        entries = app.watches.all()
                    },
                )
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun WatchRow(
    watch: PageWatch,
    onOpen: () -> Unit,
    onDelete: () -> Unit,
    onIntervalChange: (Int) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onOpen)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(watch.title.ifBlank { watch.url },
                 style = MaterialTheme.typography.bodyLarge,
                 maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(watch.url, style = MaterialTheme.typography.bodySmall,
                 color = MaterialTheme.colorScheme.outline,
                 maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(
                summary(watch),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.outline,
            )
            // Cycle through 15 / 60 / 360 minute intervals.
            val nextMins = when (watch.intervalMinutes) {
                in 0..15 -> 60
                in 16..60 -> 360
                else -> 15
            }
            TextButton(onClick = { onIntervalChange(nextMins) }) {
                Text("Every ${pretty(watch.intervalMinutes)} — tap to change")
            }
        }
        IconButton(onClick = onDelete) {
            Icon(Icons.Default.Delete, contentDescription = "Stop watching")
        }
    }
}

private fun summary(w: PageWatch): String {
    val parts = mutableListOf<String>()
    if (w.lastCheckedAt > 0) {
        parts += "checked ${ago(w.lastCheckedAt)}"
    } else {
        parts += "not yet checked"
    }
    if (w.lastChangedAt > 0) {
        parts += "last changed ${ago(w.lastChangedAt)}"
    }
    return parts.joinToString(" · ")
}

private fun ago(ts: Double): String {
    val seconds = ((System.currentTimeMillis() / 1000.0) - ts).toLong()
    return when {
        seconds < 60 -> "just now"
        seconds < 3600 -> "${seconds / 60}m ago"
        seconds < 86400 -> "${seconds / 3600}h ago"
        else -> "${seconds / 86400}d ago"
    }
}

private fun pretty(mins: Int): String = when {
    mins < 60 -> "$mins min"
    mins == 60 -> "hour"
    mins < 1440 -> "${mins / 60} hours"
    else -> "${mins / 1440} days"
}
