package com.shroudbyte.browser

import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.viewmodel.compose.viewModel
import com.shroudbyte.ShroudApplication

@Composable
fun BrowserScreen(app: ShroudApplication) {
    val vm: BrowserViewModel = viewModel(factory = BrowserViewModel.Factory)
    var urlBarText by remember(vm.currentTab?.id) {
        mutableStateOf(vm.currentTab?.url.orEmpty())
    }

    Scaffold(
        topBar = {
            BrowserTopBar(
                urlBarText = urlBarText,
                onUrlBarTextChange = { urlBarText = it },
                onGo = {
                    vm.navigate(urlBarText)
                    urlBarText = vm.currentTab?.url.orEmpty()
                },
            )
        },
        bottomBar = {
            TabStrip(
                tabs = vm.tabs,
                currentIndex = vm.currentIndex,
                onSelect = { vm.currentIndex = it },
                onClose = { vm.closeTab(it) },
                onNew = { vm.newTab() },
            )
        },
    ) { padding ->
        Box(modifier = Modifier.padding(padding).fillMaxSize()) {
            val tab = vm.currentTab
            if (tab != null) {
                key(tab.id) {
                    AndroidView(
                        modifier = Modifier.fillMaxSize(),
                        factory = { ctx ->
                            WebView(ctx).apply {
                                layoutParams = ViewGroup.LayoutParams(
                                    ViewGroup.LayoutParams.MATCH_PARENT,
                                    ViewGroup.LayoutParams.MATCH_PARENT,
                                )
                                settings.javaScriptEnabled = app.settings.load().enableJavascript
                                settings.domStorageEnabled = true
                                settings.databaseEnabled = true
                                settings.userAgentString = settings.userAgentString
                                webViewClient = ShroudWebViewClient(
                                    tab, app.settings, app.history, app.hostBlocker,
                                )
                                webChromeClient = object : WebChromeClient() {
                                    override fun onProgressChanged(view: WebView?, newProgress: Int) {
                                        tab.progress = newProgress
                                    }
                                    override fun onReceivedTitle(view: WebView?, title: String?) {
                                        if (!title.isNullOrBlank()) tab.title = title
                                    }
                                }
                                if (tab.url != "about:blank") loadUrl(tab.url)
                            }
                        },
                        update = { wv ->
                            if (wv.url != tab.url && tab.url != "about:blank") {
                                wv.loadUrl(tab.url)
                            }
                        },
                    )
                }
                if (tab.progress in 1..99) {
                    LinearProgressIndicator(
                        progress = { tab.progress / 100f },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BrowserTopBar(
    urlBarText: String,
    onUrlBarTextChange: (String) -> Unit,
    onGo: () -> Unit,
) {
    Surface(tonalElevation = 2.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = urlBarText,
                onValueChange = onUrlBarTextChange,
                modifier = Modifier
                    .weight(1f)
                    .heightIn(min = 48.dp),
                singleLine = true,
                shape = RoundedCornerShape(24.dp),
                placeholder = { Text("Search or enter URL") },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Go),
                keyboardActions = KeyboardActions(onGo = { onGo() }),
            )
            IconButton(onClick = onGo) {
                Icon(Icons.Default.KeyboardArrowRight, contentDescription = "Go")
            }
        }
    }
}

@Composable
private fun TabStrip(
    tabs: List<TabState>,
    currentIndex: Int,
    onSelect: (Int) -> Unit,
    onClose: (Int) -> Unit,
    onNew: () -> Unit,
) {
    Surface(tonalElevation = 4.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(IntrinsicSize.Min)
                .padding(vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            LazyRow(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(horizontal = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                itemsIndexed(tabs) { idx, tab ->
                    val isCurrent = idx == currentIndex
                    Surface(
                        modifier = Modifier
                            .heightIn(min = 36.dp)
                            .background(
                                if (isCurrent) MaterialTheme.colorScheme.primaryContainer
                                else MaterialTheme.colorScheme.surface
                            ),
                        shape = RoundedCornerShape(12.dp),
                    ) {
                        Row(
                            modifier = Modifier.padding(start = 10.dp, end = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            TextButton(onClick = { onSelect(idx) }) {
                                Text(
                                    text = tab.title.ifBlank { "New tab" }.take(20),
                                    maxLines = 1,
                                )
                            }
                            IconButton(
                                onClick = { onClose(idx) },
                                modifier = Modifier.size(28.dp),
                            ) {
                                Icon(
                                    Icons.Default.Close,
                                    contentDescription = "Close",
                                    modifier = Modifier.size(16.dp),
                                )
                            }
                        }
                    }
                }
            }
            IconButton(onClick = onNew) {
                Icon(Icons.Default.Add, contentDescription = "New tab")
            }
        }
    }
}

