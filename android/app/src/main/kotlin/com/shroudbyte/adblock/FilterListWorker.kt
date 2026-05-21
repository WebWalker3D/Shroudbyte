package com.shroudbyte.adblock

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.shroudbyte.ShroudApplication
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Periodic worker that refreshes the filter list cache, then hands the
 * combined host set to the live [HostBlocker] so blocking improves
 * without a relaunch.
 */
class FilterListWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val app = applicationContext as ShroudApplication
        if (!app.settings.load().enableAdblock) return@withContext Result.success()
        val hosts = app.filterListDownloader.refresh()
        // Defaults + downloaded set, all lowercased.
        app.hostBlocker.setHosts(HostBlocker.DEFAULT_HOSTS + hosts)
        Result.success()
    }

    companion object {
        private const val UNIQUE_NAME = "shroudbyte_filter_lists"

        fun ensureScheduled(context: Context) {
            val request = PeriodicWorkRequestBuilder<FilterListWorker>(
                24, TimeUnit.HOURS,
                1, TimeUnit.HOURS,    // flex
            )
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.UNMETERED)
                        .build(),
                )
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                UNIQUE_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
