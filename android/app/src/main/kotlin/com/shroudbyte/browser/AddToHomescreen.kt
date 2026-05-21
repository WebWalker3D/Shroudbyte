package com.shroudbyte.browser

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.net.Uri
import android.widget.Toast
import androidx.core.content.pm.ShortcutInfoCompat
import androidx.core.content.pm.ShortcutManagerCompat
import androidx.core.graphics.drawable.IconCompat
import com.shroudbyte.MainActivity

/**
 * Add the current page to the launcher as a pinned shortcut.
 *
 * This is the Android equivalent of the desktop client's PWA install
 * flow: a one-tap path from the open tab to a launcher icon that
 * opens the URL straight back into Shroudbyte's MainActivity (the
 * http/https intent filter is already there).
 *
 * No web app manifest parsing — we use the page title for the label
 * and a procedurally-generated initial-letter icon.
 */
object AddToHomescreen {

    fun pin(context: Context, url: String, title: String) {
        if (!ShortcutManagerCompat.isRequestPinShortcutSupported(context)) {
            Toast.makeText(
                context,
                "Your launcher doesn't support pinning shortcuts.",
                Toast.LENGTH_LONG,
            ).show()
            return
        }
        val intent = Intent(context, MainActivity::class.java).apply {
            action = Intent.ACTION_VIEW
            data = Uri.parse(url)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val label = title.ifBlank { url }
        val shortcut = ShortcutInfoCompat.Builder(context, "shroudbyte-${url.hashCode()}")
            .setShortLabel(label.take(20))
            .setLongLabel(label.take(60))
            .setIcon(IconCompat.createWithBitmap(initialIcon(label)))
            .setIntent(intent)
            .build()
        ShortcutManagerCompat.requestPinShortcut(context, shortcut, null)
    }

    /**
     * Procedural icon: a coloured square with the first letter of the
     * label in the centre. Cheap, deterministic per-URL, and good
     * enough until we wire up a real favicon fetcher.
     */
    private fun initialIcon(label: String): Bitmap {
        val size = 192
        val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)

        val seed = label.hashCode()
        val hue = ((seed % 360) + 360) % 360
        val bg = hsvToRgb(hue.toFloat(), 0.55f, 0.65f)
        canvas.drawColor(Color.TRANSPARENT)
        Paint(Paint.ANTI_ALIAS_FLAG).also { p ->
            p.color = bg
            canvas.drawRoundRect(
                RectF(0f, 0f, size.toFloat(), size.toFloat()),
                size * 0.22f, size * 0.22f, p,
            )
        }
        val letter = label.firstOrNull { it.isLetterOrDigit() }?.uppercaseChar()?.toString() ?: "S"
        val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = size * 0.55f
            textAlign = Paint.Align.CENTER
            isFakeBoldText = true
        }
        val baseline = size / 2f - (textPaint.descent() + textPaint.ascent()) / 2f
        canvas.drawText(letter, size / 2f, baseline, textPaint)
        return bmp
    }

    private fun hsvToRgb(h: Float, s: Float, v: Float): Int {
        return Color.HSVToColor(floatArrayOf(h, s, v))
    }
}
