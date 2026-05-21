package com.shroudbyte.watches

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * One WorkManager job runs every 15 minutes (the platform minimum for
 * periodic work) and looks at every watch — each watch's own interval
 * is enforced inside the worker, so we don't need a job per watch.
 */
object PageWatchScheduler {

    private const val UNIQUE_NAME = "shroudbyte_page_watch"

    fun ensureScheduled(context: Context) {
        val request = PeriodicWorkRequestBuilder<PageWatchWorker>(
            15, TimeUnit.MINUTES,
            5, TimeUnit.MINUTES,    // flex
        )
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build(),
            )
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            UNIQUE_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(UNIQUE_NAME)
    }
}
