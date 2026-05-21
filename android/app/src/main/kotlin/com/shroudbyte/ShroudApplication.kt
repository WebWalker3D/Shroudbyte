package com.shroudbyte

import android.app.Application
import com.shroudbyte.addresses.AddressBook
import com.shroudbyte.adblock.HostBlocker
import com.shroudbyte.browser.SessionRepository
import com.shroudbyte.storage.BookmarksRepository
import com.shroudbyte.storage.HistoryRepository
import com.shroudbyte.storage.SettingsRepository
import com.shroudbyte.storage.Storage

/**
 * Process-lifetime singletons. A real app would wire these through
 * Hilt / Koin; we keep DI manual to keep the build dependency-free.
 */
class ShroudApplication : Application() {

    lateinit var storage: Storage
        private set
    lateinit var settings: SettingsRepository
        private set
    lateinit var bookmarks: BookmarksRepository
        private set
    lateinit var history: HistoryRepository
        private set
    lateinit var addresses: AddressBook
        private set
    lateinit var hostBlocker: HostBlocker
        private set
    lateinit var session: SessionRepository
        private set

    override fun onCreate() {
        super.onCreate()
        storage = Storage.forContext(this)
        // Install the crash logger early so a startup crash in any of the
        // repos below still produces a recoverable report on disk.
        CrashLogger.install(storage)
        settings = SettingsRepository(storage)
        bookmarks = BookmarksRepository(storage)
        history = HistoryRepository(storage)
        addresses = AddressBook(storage)
        hostBlocker = HostBlocker()
        session = SessionRepository(storage)
    }
}
