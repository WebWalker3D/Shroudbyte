package com.shroudbyte.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.shroudbyte.ShroudApplication
import com.shroudbyte.storage.HistoryEntry

/**
 * Material-styled new-tab landing page. Replaces the blank WebView the
 * user used to see for `about:blank` — surfaces recent history + top
 * bookmarks so a tap gets them somewhere useful quickly.
 */
@Composable
fun NewTabPanel(
    app: ShroudApplication,
    onOpen: (String) -> Unit,
) {
    val bookmarks = remember { app.bookmarks.all().take(8) }
    val history = remember { app.history.load().asReversed().take(8) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Shroudbyte", style = MaterialTheme.typography.headlineMedium)
        Text(
            "Search or enter a URL above.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.outline,
        )

        if (bookmarks.isNotEmpty()) {
            Text("Bookmarks", style = MaterialTheme.typography.titleMedium)
            LazyColumn(modifier = Modifier.heightIn(max = 240.dp)) {
                items(bookmarks, key = { it.url }) { bm ->
                    QuickLink(title = bm.title, url = bm.url) { onOpen(bm.url) }
                }
            }
        }

        if (history.isNotEmpty()) {
            Text("Recent", style = MaterialTheme.typography.titleMedium)
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(history, key = { it.url + it.visitedAt }) { e ->
                    QuickLink(title = e.title.ifBlank { e.url }, url = e.url) {
                        onOpen(e.url)
                    }
                }
            }
        }
    }
}

@Composable
private fun QuickLink(title: String, url: String, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp),
    ) {
        Text(title, style = MaterialTheme.typography.bodyLarge,
             maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(url, style = MaterialTheme.typography.bodySmall,
             color = MaterialTheme.colorScheme.outline,
             maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}
