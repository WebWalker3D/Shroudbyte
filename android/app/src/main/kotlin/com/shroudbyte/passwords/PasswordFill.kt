package com.shroudbyte.passwords

import android.webkit.WebView
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject

/**
 * Fill a login form on the current page from a saved [PasswordEntry].
 * Same shape as the desktop client's auto-fill JS — look for the first
 * username + password field that's visible, set both, dispatch events.
 */
object PasswordFill {

    fun fillInto(webView: WebView, entry: PasswordEntry) {
        val payload = buildJsonObject {
            put("username", JsonPrimitive(entry.username))
            put("password", JsonPrimitive(entry.password))
        }
        val payloadJson = Json.encodeToString(
            kotlinx.serialization.json.JsonObject.serializer(), payload
        )
        val js = """
            (function(values){
              var pwd = null;
              var inputs = Array.prototype.slice.call(
                document.querySelectorAll('input')
              );
              // Find the password field first; the username is the
              // closest non-hidden text input that precedes it in DOM order.
              for (var i = inputs.length - 1; i >= 0; i--) {
                if (inputs[i].type === 'password' && isVisible(inputs[i])) {
                  pwd = inputs[i];
                  break;
                }
              }
              if (!pwd) return 0;
              var user = null;
              for (var i = inputs.indexOf(pwd) - 1; i >= 0; i--) {
                var el = inputs[i];
                if (!isVisible(el)) continue;
                var t = (el.type || 'text').toLowerCase();
                if (t === 'text' || t === 'email' || t === 'tel' || !t) {
                  user = el;
                  break;
                }
              }
              setVal(pwd, values.password);
              if (user) setVal(user, values.username);
              return 1;

              function isVisible(el) {
                if (!el || el.disabled) return false;
                var s = window.getComputedStyle(el);
                return s.display !== 'none' && s.visibility !== 'hidden'
                       && el.offsetWidth > 0 && el.offsetHeight > 0;
              }
              function setVal(el, v) {
                el.focus();
                el.value = v;
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
              }
            })($payloadJson);
        """.trimIndent()
        webView.evaluateJavascript(js, null)
    }
}
