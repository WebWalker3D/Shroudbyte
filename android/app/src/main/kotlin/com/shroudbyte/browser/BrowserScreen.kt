package com.shroudbyte.browser

import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebView
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.Star
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import com.shroudbyte.ShroudApplication
import com.shroudbyte.ui.screens.AboutScreen
import com.shroudbyte.ui.screens.AddressesScreen
import com.shroudbyte.ui.screens.BookmarksScreen
import com.shroudbyte.ui.screens.HistoryScreen
import com.shroudbyte.ui.screens.NewTabPanel
import com.shroudbyte.ui.screens.PasswordsScreen
import com.shroudbyte.ui.screens.ReaderScreen
import com.shroudbyte.ui.screens.SettingsScreen
import com.shroudbyte.ui.screens.WatchesScreen
import com.shroudbyte.ui.theme.ShroudTheme
import kotlinx.coroutines.launch

/**
 * Screen the navigation drawer can route to. The browser itself is the
 * default; the others are full-screen takeovers that snap back via the
 * top-left arrow.
 */
enum class Route { Browser, Bookmarks, History, Settings, Addresses, Passwords, About, Reader, Watches }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BrowserScreen(app: ShroudApplication, theme: ShroudTheme = ShroudTheme.Dark) {
    val vm: BrowserViewModel = viewModel(factory = BrowserViewModel.Factory)
    var route by remember { mutableStateOf(Route.Browser) }
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()

    // System back on a secondary screen returns to the browser.
    BackHandler(enabled = route != Route.Browser) {
        route = Route.Browser
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet {
                Spacer(Modifier.height(16.dp))
                DrawerItem("Bookmarks") {
                    route = Route.Bookmarks
                    scope.launch { drawerState.close() }
                }
                DrawerItem("History") {
                    route = Route.History
                    scope.launch { drawerState.close() }
                }
                DrawerItem("Addresses") {
                    route = Route.Addresses
                    scope.launch { drawerState.close() }
                }
                DrawerItem("Passwords") {
                    route = Route.Passwords
                    scope.launch { drawerState.close() }
                }
                DrawerItem("Page watches") {
                    route = Route.Watches
                    scope.launch { drawerState.close() }
                }
                DrawerItem("Settings") {
                    route = Route.Settings
                    scope.launch { drawerState.close() }
                }
                DrawerItem("About") {
                    route = Route.About
                    scope.launch { drawerState.close() }
                }
                HorizontalDivider()
                DrawerItem("Find on page") {
                    vm.toggleFindBar()
                    scope.launch { drawerState.close() }
                }
                DrawerItem("Reader mode") {
                    scope.launch { drawerState.close() }
                    vm.openReader { ok ->
                        if (ok) route = Route.Reader
                    }
                }
                DrawerItem("Watch this page") {
                    val tab = vm.currentTab
                    if (tab != null && tab.url.isNotBlank() && tab.url != "about:blank") {
                        app.watches.add(tab.url, tab.title)
                    }
                    scope.launch { drawerState.close() }
                }
            }
        },
    ) {
        when (route) {
            Route.Browser -> BrowserContent(
                app = app,
                vm = vm,
                onOpenDrawer = { scope.launch { drawerState.open() } },
            )
            Route.Bookmarks -> BookmarksScreen(
                app = app,
                onBack = { route = Route.Browser },
                onOpen = { url ->
                    vm.navigate(url)
                    route = Route.Browser
                },
            )
            Route.History -> HistoryScreen(
                app = app,
                onBack = { route = Route.Browser },
                onOpen = { url ->
                    vm.navigate(url)
                    route = Route.Browser
                },
            )
            Route.Addresses -> AddressesScreen(
                app = app,
                onBack = { route = Route.Browser },
                onFill = { addressId ->
                    val tab = vm.currentTab ?: return@AddressesScreen
                    val wv = tab.webView ?: return@AddressesScreen
                    app.addresses.get(addressId)?.let { addr ->
                        com.shroudbyte.addresses.AddressFill.fillInto(wv, addr)
                    }
                    route = Route.Browser
                },
            )
            Route.Settings -> SettingsScreen(
                app = app,
                onBack = { route = Route.Browser },
            )
            Route.Passwords -> PasswordsScreen(
                app = app,
                onBack = { route = Route.Browser },
            )
            Route.About -> AboutScreen(
                app = app,
                onBack = { route = Route.Browser },
            )
            Route.Watches -> WatchesScreen(
                app = app,
                onBack = { route = Route.Browser },
                onOpen = { url ->
                    vm.navigate(url)
                    route = Route.Browser
                },
            )
            Route.Reader -> {
                val article = vm.readerArticle
                if (article == null) {
                    // Extraction failed or stale; bounce back.
                    route = Route.Browser
                } else {
                    ReaderScreen(
                        article = article,
                        originalUrl = vm.currentTab?.url.orEmpty(),
                        theme = theme,
                        onBack = {
                            vm.closeReader()
                            route = Route.Browser
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun BrowserContent(
    app: ShroudApplication,
    vm: BrowserViewModel,
    onOpenDrawer: () -> Unit,
) {
    var urlBarText by remember(vm.currentTab?.id, vm.currentTab?.url) {
        mutableStateOf(vm.currentTab?.url.orEmpty())
    }

    // System back goes to the previous page in the current tab when
    // available; only falls through to default activity-finish behaviour
    // (closing the app) when there's nowhere to go back to.
    BackHandler(enabled = vm.currentTab?.canGoBack == true) {
        vm.back()
    }

    var contextHit by remember { mutableStateOf<LinkHit?>(null) }
    val ctx = LocalContext.current

    LinkContextMenu(
        hit = contextHit,
        onDismiss = { contextHit = null },
        onOpenInNewTab = { url -> vm.newTab(url) },
        onCopy = { url -> copyToClipboard(ctx, url) },
        onShare = { url -> shareUrl(ctx, url) },
        onDownloadImage = { url ->
            Downloads.enqueue(ctx, url, vm.currentTab?.webView?.settings?.userAgentString,
                              null, null)
        },
    )

    Scaffold(
        topBar = {
            BrowserTopBar(
                vm = vm,
                urlBarText = urlBarText,
                onUrlBarTextChange = { urlBarText = it },
                onGo = {
                    vm.navigate(urlBarText)
                    urlBarText = vm.currentTab?.url.orEmpty()
                },
                onOpenDrawer = onOpenDrawer,
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
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            if (vm.findBarVisible) {
                FindBar(
                    onQueryChange = { vm.find(it) },
                    onNext = { vm.findNext(true) },
                    onPrev = { vm.findNext(false) },
                    onClose = { vm.toggleFindBar() },
                )
            }
            if (vm.autofillSuggestions.isNotEmpty()) {
                AutofillBanner(
                    suggestions = vm.autofillSuggestions,
                    onPick = { vm.applyAutofill(it) },
                    onDismiss = { vm.dismissAutofill() },
                )
            }
            Box(modifier = Modifier.fillMaxSize()) {
            val tab = vm.currentTab
            if (tab != null) {
                if (tab.url.isBlank() || tab.url == "about:blank") {
                    NewTabPanel(app = app, onOpen = { vm.navigate(it) })
                } else {
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
                                    webViewClient = ShroudWebViewClient(
                                        tab, app.settings, app.history, app.hostBlocker,
                                    ).apply {
                                        onPageFinishedExtra = { vm.maybeShowAutofill() }
                                    }
                                    webChromeClient = ShroudWebChromeClient(ctx, tab)
                                    setDownloadListener { url, userAgent, contentDisposition,
                                                           mimeType, _ ->
                                        Downloads.enqueue(ctx, url, userAgent,
                                                          contentDisposition, mimeType)
                                    }
                                    setOnLongClickListener {
                                        val hit = (it as WebView).captureHit()
                                        if (hit.isLink || hit.isImage) {
                                            contextHit = hit
                                            true
                                        } else false
                                    }
                                    tab.webView = this
                                    loadUrl(tab.url)
                                }
                            },
                            update = { wv ->
                                tab.canGoBack = wv.canGoBack()
                                tab.canGoForward = wv.canGoForward()
                                if (wv.url != tab.url) {
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
    }
}

@Composable
private fun AutofillBanner(
    suggestions: List<com.shroudbyte.passwords.PasswordEntry>,
    onPick: (com.shroudbyte.passwords.PasswordEntry) -> Unit,
    onDismiss: () -> Unit,
) {
    Surface(
        color = MaterialTheme.colorScheme.primaryContainer,
        tonalElevation = 4.dp,
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "Fill credentials for this site",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.weight(1f),
                )
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Default.Close, contentDescription = "Dismiss")
                }
            }
            for (s in suggestions) {
                TextButton(
                    onClick = { onPick(s) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        text = s.username +
                            (if (s.name.isNotBlank() && s.name != s.username) "  •  ${s.name}" else ""),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FindBar(
    onQueryChange: (String) -> Unit,
    onNext: () -> Unit,
    onPrev: () -> Unit,
    onClose: () -> Unit,
) {
    var text by remember { mutableStateOf("") }
    Surface(tonalElevation = 2.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = {
                    text = it
                    onQueryChange(it)
                },
                modifier = Modifier.weight(1f),
                singleLine = true,
                placeholder = { Text("Find on page") },
            )
            IconButton(onClick = onPrev) {
                Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Previous")
            }
            IconButton(onClick = onNext) {
                Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Next")
            }
            IconButton(onClick = onClose) {
                Icon(Icons.Default.Close, contentDescription = "Close find bar")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BrowserTopBar(
    vm: BrowserViewModel,
    urlBarText: String,
    onUrlBarTextChange: (String) -> Unit,
    onGo: () -> Unit,
    onOpenDrawer: () -> Unit,
) {
    val tab = vm.currentTab
    Surface(tonalElevation = 2.dp) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onOpenDrawer) {
                    Icon(Icons.Default.Menu, contentDescription = "Menu")
                }
                IconButton(onClick = { vm.back() }, enabled = tab?.canGoBack == true) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Back")
                }
                IconButton(onClick = { vm.forward() }, enabled = tab?.canGoForward == true) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Forward")
                }
                IconButton(onClick = { vm.reload() }) {
                    Icon(Icons.Default.Refresh, contentDescription = "Reload")
                }
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 4.dp),
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
                IconButton(onClick = { vm.toggleBookmark() }) {
                    val starred = vm.isCurrentBookmarked()
                    Icon(
                        imageVector = if (starred)
                            Icons.Filled.Star
                        else
                            Icons.Outlined.Star,
                        contentDescription = if (starred) "Remove bookmark" else "Bookmark",
                    )
                }
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

@Composable
private fun DrawerItem(label: String, onClick: () -> Unit) {
    NavigationDrawerItem(
        label = { Text(label) },
        selected = false,
        onClick = onClick,
        modifier = Modifier.padding(horizontal = 12.dp),
    )
}
