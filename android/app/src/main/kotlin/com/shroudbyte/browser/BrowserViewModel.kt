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
        if (tabs.isEmpty()) {
            tabs += TabState(app.settings.load().searchEngine
                .substringBefore("/?")
                .ifBlank { "about:blank" })
        }
    }

    fun newTab(url: String = "about:blank") {
        tabs += TabState(url)
        currentIndex = tabs.lastIndex
    }

    fun closeTab(index: Int) {
        if (tabs.size <= 1) {
            // Keep at least one tab open; replace its content instead.
            tabs[0] = TabState()
            currentIndex = 0
            return
        }
        val wasCurrent = index == currentIndex
        tabs.removeAt(index)
        if (wasCurrent) {
            currentIndex = (index).coerceAtMost(tabs.lastIndex)
        } else if (index < currentIndex) {
            _currentIndex.value = currentIndex - 1
        }
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
