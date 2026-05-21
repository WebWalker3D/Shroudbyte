package com.shroudbyte.browser

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.webkit.WebView
import android.widget.Toast
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.unit.dp

/**
 * Data captured from a WebView long-press. Image hits also have a `link`
 * field if the image is inside an anchor element.
 */
data class LinkHit(val type: Int, val link: String?, val image: String?) {
    val isImage: Boolean get() = type == WebView.HitTestResult.IMAGE_TYPE ||
            type == WebView.HitTestResult.SRC_IMAGE_ANCHOR_TYPE
    val isLink: Boolean get() = link != null
}

/**
 * Build a [LinkHit] from the WebView's hit-test result. The WebView API
 * for src-image-anchor is awkward — the anchor URL is delivered via a
 * Message-based handler, so callers must opt in by invoking [requestImageAnchorUrl].
 */
fun WebView.captureHit(): LinkHit {
    val r = hitTestResult
    return LinkHit(
        type = r.type,
        link = when (r.type) {
            WebView.HitTestResult.SRC_ANCHOR_TYPE,
            WebView.HitTestResult.SRC_IMAGE_ANCHOR_TYPE -> r.extra
            else -> null
        },
        image = when (r.type) {
            WebView.HitTestResult.IMAGE_TYPE,
            WebView.HitTestResult.SRC_IMAGE_ANCHOR_TYPE -> r.extra
            else -> null
        },
    )
}

@Composable
fun LinkContextMenu(
    hit: LinkHit?,
    onDismiss: () -> Unit,
    onOpenInNewTab: (String) -> Unit,
    onCopy: (String) -> Unit,
    onShare: (String) -> Unit,
    onDownloadImage: (String) -> Unit,
) {
    if (hit == null) return
    val anchor = hit.link ?: hit.image ?: return
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(anchor, maxLines = 2,
                 overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
        },
        text = {
            androidx.compose.foundation.layout.Column {
                if (hit.isLink) {
                    Action("Open in new tab") {
                        onOpenInNewTab(hit.link!!); onDismiss()
                    }
                    Action("Copy link") {
                        onCopy(hit.link!!); onDismiss()
                    }
                    Action("Share link") {
                        onShare(hit.link!!); onDismiss()
                    }
                }
                if (hit.isImage && hit.image != null) {
                    if (hit.isLink) HorizontalDivider()
                    Action("Open image in new tab") {
                        onOpenInNewTab(hit.image); onDismiss()
                    }
                    Action("Copy image URL") {
                        onCopy(hit.image); onDismiss()
                    }
                    Action("Save image") {
                        onDownloadImage(hit.image); onDismiss()
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}

@Composable
private fun Action(label: String, onClick: () -> Unit) {
    TextButton(
        onClick = onClick,
        modifier = androidx.compose.ui.Modifier.fillMaxWidth(),
    ) {
        Text(
            label,
            modifier = androidx.compose.ui.Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
            textAlign = androidx.compose.ui.text.style.TextAlign.Start,
        )
    }
}

// ---------------------------------------------------------------------------
// Plain-Kotlin helpers used by the menu actions.
// ---------------------------------------------------------------------------

fun copyToClipboard(ctx: Context, text: String) {
    val cm = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("Shroudbyte", text))
    Toast.makeText(ctx, "Copied", Toast.LENGTH_SHORT).show()
}

fun shareUrl(ctx: Context, url: String) {
    val send = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, url)
    }
    ctx.startActivity(Intent.createChooser(send, "Share link").apply {
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    })
}
