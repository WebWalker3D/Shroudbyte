package com.shroudbyte.ui.screens

import android.view.ViewGroup
import android.webkit.WebView
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.viewinterop.AndroidView
import com.shroudbyte.browser.ReaderArticle
import com.shroudbyte.ui.theme.DarkPalette
import com.shroudbyte.ui.theme.HighContrastPalette
import com.shroudbyte.ui.theme.LightPalette
import com.shroudbyte.ui.theme.ShroudTheme

/**
 * Render the extracted reader article in a minimal WebView so the
 * existing CSS-driven typography looks right. Compose Text isn't a
 * great fit for arbitrary article HTML (lots of inline markup, lists,
 * blockquotes, images); a sandboxed WebView with no JS and an
 * inlined stylesheet stays readable and lightweight.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReaderScreen(
    article: ReaderArticle,
    originalUrl: String,
    theme: ShroudTheme,
    onBack: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Reader") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Box(modifier = Modifier.padding(padding).fillMaxSize()) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    WebView(ctx).apply {
                        layoutParams = ViewGroup.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT,
                        )
                        // No JS, no DOM storage — the article HTML is
                        // already neutral after the cloneNode/strip pass.
                        settings.javaScriptEnabled = false
                        settings.domStorageEnabled = false
                    }
                },
                update = { wv ->
                    wv.loadDataWithBaseURL(
                        originalUrl,
                        buildHtml(article, originalUrl, theme),
                        "text/html",
                        "utf-8",
                        null,
                    )
                },
            )
        }
    }
}

private fun buildHtml(article: ReaderArticle, originalUrl: String, theme: ShroudTheme): String {
    val bgColor: Color; val fgColor: Color; val accentColor: Color
    when (theme) {
        ShroudTheme.Dark -> {
            bgColor = DarkPalette.BgDark; fgColor = DarkPalette.Text; accentColor = DarkPalette.Accent
        }
        ShroudTheme.Light -> {
            bgColor = LightPalette.BgDark; fgColor = LightPalette.Text; accentColor = LightPalette.Accent
        }
        ShroudTheme.HighContrast -> {
            bgColor = HighContrastPalette.BgDark; fgColor = HighContrastPalette.Text; accentColor = HighContrastPalette.Accent
        }
    }
    val bg = hex(bgColor)
    val fg = hex(fgColor)
    val accent = hex(accentColor)
    return """
        <!DOCTYPE html>
        <html><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
          html, body { margin: 0; padding: 0; background: $bg; color: $fg; }
          body {
            font-family: Georgia, 'Noto Serif', 'Times New Roman', serif;
            font-size: 18px;
            line-height: 1.7;
            padding: 24px 18px 48px;
          }
          h1 { font-size: 28px; line-height: 1.25; margin: 0 0 4px; }
          .byline, .site { color: ${fg}99; font-size: 13px; margin-bottom: 12px; }
          .site a { color: $accent; text-decoration: none; }
          p { margin: 0 0 1em; }
          img, video { max-width: 100%; height: auto; border-radius: 6px; }
          blockquote {
            border-left: 3px solid $accent; margin: 1em 0; padding: 4px 14px;
            color: ${fg}cc;
          }
          a { color: $accent; }
          pre, code { font-family: 'JetBrains Mono', monospace; }
          pre {
            background: ${fg}10; padding: 12px; border-radius: 6px;
            overflow-x: auto;
          }
          h2, h3, h4 { margin: 1.4em 0 0.4em; }
        </style></head>
        <body>
          <h1>${esc(article.title)}</h1>
          ${if (article.byline.isNotBlank())
              "<div class='byline'>${esc(article.byline)}</div>" else ""}
          <div class='site'>
            <a href="${esc(originalUrl)}">${esc(article.siteName)}</a>
          </div>
          ${article.content}
        </body></html>
    """.trimIndent()
}

private fun esc(s: String): String =
    s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
     .replace("\"", "&quot;").replace("'", "&#39;")

private fun hex(color: Color): String {
    val rgb = color.toArgb() and 0xFFFFFF
    return "#%06x".format(rgb)
}
