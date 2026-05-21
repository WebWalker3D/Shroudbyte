package com.shroudbyte.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

/**
 * Shroudbyte's three themes wired through a Material3 ColorScheme.
 *
 * The desktop client lets the user pick Dark / Light / High contrast in
 * Settings; on Android we honor the system dark-mode pref by default
 * and let the same setting override it.
 */
enum class ShroudTheme { Dark, Light, HighContrast }

@Composable
fun ShroudbyteTheme(
    theme: ShroudTheme = if (isSystemInDarkTheme()) ShroudTheme.Dark else ShroudTheme.Light,
    content: @Composable () -> Unit,
) {
    val scheme = when (theme) {
        ShroudTheme.Dark -> darkColorScheme(
            background = DarkPalette.BgDark,
            surface = DarkPalette.BgCard,
            primary = DarkPalette.Accent,
            onBackground = DarkPalette.Text,
            onSurface = DarkPalette.Text,
            outline = DarkPalette.Border,
            error = DarkPalette.Red,
        )
        ShroudTheme.Light -> lightColorScheme(
            background = LightPalette.BgDark,
            surface = LightPalette.BgCard,
            primary = LightPalette.Accent,
            onBackground = LightPalette.Text,
            onSurface = LightPalette.Text,
            outline = LightPalette.Border,
            error = LightPalette.Red,
        )
        ShroudTheme.HighContrast -> darkColorScheme(
            background = HighContrastPalette.BgDark,
            surface = HighContrastPalette.BgCard,
            primary = HighContrastPalette.Accent,
            onBackground = HighContrastPalette.Text,
            onSurface = HighContrastPalette.Text,
            outline = HighContrastPalette.Border,
            error = HighContrastPalette.Red,
        )
    }
    MaterialTheme(colorScheme = scheme, content = content)
}
