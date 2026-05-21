package com.shroudbyte.addresses

import android.webkit.WebView
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject

/**
 * Drive an Android WebView's form fields from a saved [Address].
 *
 * The desktop client constructs an equivalent JS payload in
 * `browser/mixins/page_features.py`; this version is the same logic in
 * one place so the on-device behaviour stays consistent.
 */
object AddressFill {

    /** Inject + evaluate a fill script into [webView]; safe to call from the UI thread. */
    fun fillInto(webView: WebView, address: Address) {
        val payload = buildJsonObject {
            for ((k, v) in address.fields) put(k, JsonPrimitive(v))
        }
        val payloadJson = Json.encodeToString(
            kotlinx.serialization.json.JsonObject.serializer(), payload
        )
        // Same shape as the desktop runJavaScript() payload — guards
        // against null, dispatches input/change so React-style frameworks
        // see the value, and returns the count of fields filled.
        val js = """
            (function(values){
              var filled = 0;
              document.querySelectorAll(
                'input[autocomplete], textarea[autocomplete], select[autocomplete]'
              ).forEach(function(el){
                var key = el.getAttribute('autocomplete');
                if (key && values[key] != null) {
                  el.focus();
                  el.value = values[key];
                  el.dispatchEvent(new Event('input', {bubbles:true}));
                  el.dispatchEvent(new Event('change', {bubbles:true}));
                  filled++;
                }
              });
              return filled;
            })($payloadJson);
        """.trimIndent()
        webView.evaluateJavascript(js, null)
    }
}
