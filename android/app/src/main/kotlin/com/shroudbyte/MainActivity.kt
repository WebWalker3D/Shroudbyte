package com.shroudbyte

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.shroudbyte.browser.BrowserScreen
import com.shroudbyte.ui.theme.ShroudTheme
import com.shroudbyte.ui.theme.ShroudbyteTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as ShroudApplication
        val themeName = app.settings.load().theme
        val theme = when (themeName) {
            "light" -> ShroudTheme.Light
            "high_contrast" -> ShroudTheme.HighContrast
            else -> ShroudTheme.Dark
        }
        setContent {
            ShroudbyteTheme(theme = theme) {
                Surface(modifier = Modifier.fillMaxSize()) {
                    BrowserScreen(app)
                }
            }
        }
    }
}
