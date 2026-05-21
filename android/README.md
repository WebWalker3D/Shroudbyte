# Shroudbyte (Android — scaffold)

A Kotlin + Jetpack Compose port of the desktop browser. **This is a
starting point, not feature parity.** What's here:

- Gradle 8.5 / Kotlin 2.0 / Android Studio Iguana+ project layout
- Material3 + Compose UI with three themes (Dark / Light / High-contrast)
  mirroring `browser/style.py`
- WebView-backed browser screen with address bar + bottom tab strip
- Storage layer mirroring `browser/storage.py` (JSON-backed Settings,
  Bookmarks, History)
- Encrypted address book mirroring `browser/addresses.py` —
  byte-compatible file format (version || nonce || ciphertext+tag)
  so a future cross-platform sync can use the same `addresses.dat`
- Host-list adblock and tracking-parameter stripping
- 25+ JUnit tests for the non-Android-specific modules

## What's NOT here yet (vs. desktop)

- shroud:// internal pages — the desktop client has 19; Android UI is
  raw Compose for now
- Full ABP filter engine (only host-list blocking)
- Privacy Dashboard / Permission Ledger / Page Watch / WARC / PWA /
  named sessions / extensions / profiles
- Crash recovery prompt, update checker, i18n catalogs
- Fingerprint resistance JS, annoyance shield JS, form-draft auto-save
- DNS-over-HTTPS / Shroud DNS (would need a `VpnService` on Android)
- Password manager UI (vault crypto is ported, dialogs aren't)

The data model and crypto are deliberately byte-compatible with the
desktop client where it makes sense, so a future "Import from desktop"
flow can drop in.

## Building

Open `android/` in **Android Studio Iguana (2024.3) or newer**, let it
download the SDK + Gradle dependencies, and Run on a device/emulator
running Android 8.0 (API 26) or higher.

Or from the command line:

```bash
cd android
./gradlew assembleDebug
# Output APK: app/build/outputs/apk/debug/app-debug.apk
```

The `gradlew` wrapper script must be present (a fresh Android Studio
project generates it; or run `gradle wrapper --gradle-version 8.10`).

## Tests

```bash
./gradlew test            # JVM unit tests
./gradlew connectedCheck  # instrumented tests on a connected device
```

## Layout

```
android/
├── app/
│   ├── build.gradle.kts
│   └── src/
│       ├── main/
│       │   ├── AndroidManifest.xml
│       │   ├── kotlin/com/shroudbyte/
│       │   │   ├── MainActivity.kt
│       │   │   ├── ShroudApplication.kt
│       │   │   ├── browser/      # BrowserScreen, ViewModel, WebViewClient
│       │   │   ├── storage/      # Storage, Settings, Bookmarks, History
│       │   │   ├── addresses/    # AddressBook (encrypted)
│       │   │   ├── crypto/       # AES-256-GCM (byte-compat with desktop)
│       │   │   ├── adblock/      # HostBlocker + TrackingParams
│       │   │   └── ui/theme/     # Color, Theme (Dark/Light/HighContrast)
│       │   └── res/
│       └── test/kotlin/com/shroudbyte/
│           ├── crypto/CryptoTest.kt
│           ├── storage/BookmarksTest.kt
│           ├── addresses/AddressBookTest.kt
│           └── adblock/HostBlockerTest.kt
├── build.gradle.kts
├── settings.gradle.kts
└── gradle.properties
```
