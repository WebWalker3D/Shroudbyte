package com.shroudbyte.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Palettes mirroring `browser/style.py` — three themes: dark (default),
 * light, and high-contrast. Compose drives the live UI from these values
 * via [ShroudbyteTheme].
 */
object DarkPalette {
    val BgDark    = Color(0xFF0C0B10)
    val BgMid     = Color(0xFF14131A)
    val BgCard    = Color(0xFF1C1B24)
    val Border    = Color(0xFF282633)
    val Accent    = Color(0xFFCD8D6A)
    val Text      = Color(0xFFEDE8E3)
    val TextDim   = Color(0xFF8A8494)
    val Green     = Color(0xFF7DB88F)
    val Red       = Color(0xFFD96B6B)
}

object LightPalette {
    val BgDark    = Color(0xFFF0EEEB)
    val BgMid     = Color(0xFFFFFFFF)
    val BgCard    = Color(0xFFF7F5F2)
    val Border    = Color(0xFFDDD8D0)
    val Accent    = Color(0xFFB87A5A)
    val Text      = Color(0xFF2C2520)
    val TextDim   = Color(0xFF6B6460)
    val Green     = Color(0xFF3A8A52)
    val Red       = Color(0xFFC04040)
}

object HighContrastPalette {
    val BgDark    = Color(0xFF000000)
    val BgMid     = Color(0xFF000000)
    val BgCard    = Color(0xFF0A0A0A)
    val Border    = Color(0xFFFFFFFF)
    val Accent    = Color(0xFFFFFF00)
    val Text      = Color(0xFFFFFFFF)
    val TextDim   = Color(0xFFE0E0E0)
    val Green     = Color(0xFF00FF7F)
    val Red       = Color(0xFFFF5252)
}
