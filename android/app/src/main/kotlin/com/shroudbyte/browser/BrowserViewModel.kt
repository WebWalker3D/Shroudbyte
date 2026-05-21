package com.shroudbyte.browser

import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.shroudbyte.ShroudApplication
import com.shroudbyte.passwords.LoginFormDetector
import com.shroudbyte.passwords.PasswordEntry
import com.shroudbyte.passwords.PasswordFill

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

    // ------------------------------------------------------------------
    // Reader mode
    // ------------------------------------------------------------------

    private val _readerArticle = mutableStateOf<ReaderArticle?>(null)
    val readerArticle: ReaderArticle? get() = _readerArticle.value

    fun openReader(onReady: (Boolean) -> Unit) {
        val wv = currentTab?.webView
        if (wv == null) {
            onReady(false)
            return
        }
        Reader.extract(wv) { article ->
            _readerArticle.value = article
            onReady(article != null)
        }
    }

    fun closeReader() {
        _readerArticle.value = null
    }

    // ------------------------------------------------------------------
    // Autofill suggestion banner
    //
    // After a tab finishes loading we run a JS probe to decide whether
    // a 'Fill credentials' banner should appear; the banner offers any
    // vault entries that match the current host.
    // ------------------------------------------------------------------

    private val _autofillSuggestions = mutableStateOf<List<PasswordEntry>>(emptyList())
    val autofillSuggestions: List<PasswordEntry> get() = _autofillSuggestions.value
    private val _autofillBannerDismissed = mutableStateOf<String?>(null)
    private val dismissedForTab: String? get() = _autofillBannerDismissed.value

    fun maybeShowAutofill() {
        val tab = currentTab ?: return
        val wv = tab.webView ?: return
        if (!app.vault.isUnlocked) {
            _autofillSuggestions.value = emptyList()
            return
        }
        val matches = app.vault.forUrl(tab.url)
        if (matches.isEmpty()) {
            _autofillSuggestions.value = emptyList()
            return
        }
        if (_autofillBannerDismissed.value == tab.id + "@" + tab.url) {
            // Already dismissed for this exact load; don't re-pester.
            return
        }
        LoginFormDetector.probe(wv) { present ->
            _autofillSuggestions.value = if (present) matches else emptyList()
        }
    }

    fun applyAutofill(entry: PasswordEntry) {
        val wv = currentTab?.webView ?: return
        PasswordFill.fillInto(wv, entry)
        app.vault.touch(entry.id)
        _autofillSuggestions.value = emptyList()
        currentTab?.let { _autofillBannerDismissed.value = it.id + "@" + it.url }
    }

    fun dismissAutofill() {
        _autofillSuggestions.value = emptyList()
        currentTab?.let { _autofillBannerDismissed.value = it.id + "@" + it.url }
    }

    // ------------------------------------------------------------------
    // Find-in-page
    // ------------------------------------------------------------------

    private val _findBarVisible = mutableStateOf(false)
    val findBarVisible: Boolean get() = _findBarVisible.value

    fun toggleFindBar() {
        _findBarVisible.value = !_findBarVisible.value
        if (!_findBarVisible.value) currentTab?.webView?.clearMatches()
    }

    fun find(query: String) {
        val wv = currentTab?.webView ?: return
        if (query.isEmpty()) wv.clearMatches() else wv.findAllAsync(query)
    }

    fun findNext(forward: Boolean) {
        currentTab?.webView?.findNext(forward)
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
