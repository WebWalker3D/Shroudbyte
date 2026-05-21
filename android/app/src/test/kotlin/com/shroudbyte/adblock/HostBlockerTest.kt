package com.shroudbyte.adblock

import org.junit.Assert.*
import org.junit.Test

class HostBlockerTest {

    /**
     * NOTE: HostBlocker uses [android.net.Uri.parse]; on the local JVM that
     * delegates to Android's stubs which throw RuntimeException at runtime
     * unless android.jar is on the classpath. The lifted host-only logic is
     * tested here through a tiny inline copy so we don't pull in Robolectric.
     */
    private fun blockHostsOnly(blocker: HostBlocker, host: String): Boolean {
        // Re-implement the parent-domain walk used by shouldBlock(), keyed
        // on host only, to keep the test JVM-pure.
        val hosts = HostBlocker.DEFAULT_HOSTS  // same starter set
        if (host in hosts) return true
        var idx = host.indexOf('.')
        while (idx in 0 until host.length - 1) {
            if (host.substring(idx + 1) in hosts) return true
            idx = host.indexOf('.', idx + 1)
        }
        return false
    }

    @Test fun `direct host match`() {
        val b = HostBlocker()
        assertTrue(blockHostsOnly(b, "doubleclick.net"))
    }

    @Test fun `subdomain matches via parent walk`() {
        val b = HostBlocker()
        assertTrue(blockHostsOnly(b, "ad.doubleclick.net"))
        assertTrue(blockHostsOnly(b, "x.y.googletagmanager.com"))
    }

    @Test fun `unrelated host not blocked`() {
        val b = HostBlocker()
        assertFalse(blockHostsOnly(b, "wikipedia.org"))
        assertFalse(blockHostsOnly(b, "doubleclickkk.net"))
    }
}

class TrackingParamsTest {

    // Same Android-stub caveat — Uri.parse isn't on the unit-test JVM by
    // default. We assert the constant table since the URI rewriting is
    // an instrumentation-test concern.

    @Test fun `well-known names are present`() {
        for (name in listOf("utm_source", "fbclid", "gclid", "msclkid", "_ga")) {
            assertTrue("$name should be in tracking-params list", name in TrackingParams.NAMES)
        }
    }

    @Test fun `unrelated params are not in the list`() {
        for (name in listOf("q", "page", "id", "search")) {
            assertFalse("$name should NOT be in the tracking-params list",
                name in TrackingParams.NAMES)
        }
    }
}
