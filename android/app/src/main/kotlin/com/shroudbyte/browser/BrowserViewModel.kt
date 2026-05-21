package com.shroudbyte.browser

import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.shroudbyte.ShroudApplication

/**
 * The top-level browser state — tabs, current tab index, address-bar
 * text. Compose observes the [tabs] snapshot list and the [currentIndex]
 * MutableState; URL bar text is local to the address-bar composable.
 */
class BrowserViewModel(private val app: ShroudApplication) : AndroidViewModel(app) {

    val tabs = mutableStateListOf<TabState>()
    private val _currentIndex = mutableStateOf(0)
    var currentIndex: Int
        get() = _currentIndex.value
        set(value) {
            _currentIndex.value = value
            tabs.getOrNull(value)?.lastActive = System.currentTimeMillis()
        }

    val currentTab: TabState?
        get() = tabs.getOrNull(currentIndex)

    init {
        // Restore the previous session if it produced any tabs.
        if (app.settings.load().restoreSession) {
            for (saved in app.session.load()) {
                tabs += TabState(saved.url).also { it.title = saved.title }
            }
        }
        if (tabs.isEmpty()) tabs += TabState()
    }

    fun newTab(url: String = "about:blank") {
        tabs += TabState(url)
        currentIndex = tabs.lastIndex
        persist()
    }

    fun closeTab(index: Int) {
        tabs.getOrNull(index)?.webView = null
        if (tabs.size <= 1) {
            tabs[0] = TabState()
            currentIndex = 0
            persist()
            return
        }
        val wasCurrent = index == currentIndex
        tabs.removeAt(index)
        if (wasCurrent) {
            currentIndex = index.coerceAtMost(tabs.lastIndex)
        } else if (index < currentIndex) {
            _currentIndex.value = currentIndex - 1
        }
        persist()
    }

    /** Save the open tabs to disk. Cheap; called after every nav and close. */
    fun persist() {
        app.session.save(tabs.toList())
    }

    /** Resolve a URL-bar entry to a navigable URL, falling back to a search. */
    fun resolveQuery(query: String): String {
        val trimmed = query.trim()
        if (trimmed.isEmpty()) return "about:blank"
        // Heuristic: looks like a host if it contains a dot and no spaces.
        if (trimmed.contains(' ').not() && trimmed.contains('.')) {
            return if (trimmed.startsWith("http")) trimmed else "https://$trimmed"
        }
        if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            return trimmed
        }
        val template = app.settings.load().searchEngine
        return template.replace("{q}", java.net.URLEncoder.encode(trimmed, "UTF-8"))
    }

    fun navigate(url: String) {
        val tab = currentTab ?: return
        val resolved = resolveQuery(url)
        tab.url = resolved
        tab.lastActive = System.currentTimeMillis()
        // History is recorded on page-load callback, not here, so we
        // capture the post-redirect URL.
        persist()
    }

    // ------------------------------------------------------------------
    // Tab actions driven by the toolbar (back / forward / reload / bookmark)
    // ------------------------------------------------------------------

    fun back() {
        val tab = currentTab ?: return
        if (tab.canGoBack) tab.webView?.goBack()
    }

    fun forward() {
        val tab = currentTab ?: return
        if (tab.canGoForward) tab.webView?.goForward()
    }

    fun reload() {
        currentTab?.webView?.reload()
    }

    fun toggleBookmark(): Boolean {
        val tab = currentTab ?: return false
        val url = tab.url
        if (url.isBlank() || url == "about:blank") return false
        return if (app.bookmarks.isBookmarked(url)) {
            app.bookmarks.remove(url)
            false
        } else {
            app.bookmarks.add(tab.title.ifBlank { url }, url)
            true
        }
    }

    fun isCurrentBookmarked(): Boolean {
        val url = currentTab?.url ?: return false
        return app.bookmarks.isBookmarked(url)
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY]
                    as ShroudApplication
                BrowserViewModel(app)
            }
        }
    }
}
