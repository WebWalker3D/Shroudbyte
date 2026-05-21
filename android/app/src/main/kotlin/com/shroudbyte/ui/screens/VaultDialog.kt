package com.shroudbyte.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.shroudbyte.passwords.PasswordVault

/**
 * Single dialog handling both first-run setup and subsequent unlocks
 * for [PasswordVault]. Caller decides which based on `vault.isSetUp()`.
 *
 * Setup requires the password to be entered twice (>= 8 chars); unlock
 * requires only the master password and reports a failure inline.
 */
@Composable
fun VaultDialog(
    vault: PasswordVault,
    onCancel: () -> Unit,
    onUnlocked: () -> Unit,
) {
    val isSetup = !vault.isSetUp()
    var password by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    fun submit() {
        if (busy) return
        busy = true
        error = null
        if (isSetup) {
            when {
                password.length < 8 -> error = "Use at least 8 characters."
                password != confirm -> error = "Passwords don't match."
                else -> {
                    try {
                        vault.setup(password)
                        onUnlocked()
                    } catch (e: Exception) {
                        error = e.message ?: "Could not create vault."
                    }
                }
            }
        } else {
            if (vault.unlock(password)) onUnlocked()
            else error = "Wrong master password."
        }
        busy = false
    }

    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text(if (isSetup) "Create password vault" else "Unlock vault") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    if (isSetup)
                        "Your master password protects every saved credential. " +
                        "There is no recovery if you forget it."
                    else
                        "Enter your master password to unlock the vault.",
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it; error = null },
                    label = { Text("Master password") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Password,
                        imeAction = if (isSetup) ImeAction.Next else ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(onDone = { submit() }),
                )
                if (isSetup) {
                    OutlinedTextField(
                        value = confirm,
                        onValueChange = { confirm = it; error = null },
                        label = { Text("Confirm password") },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Password,
                            imeAction = ImeAction.Done,
                        ),
                        keyboardActions = KeyboardActions(onDone = { submit() }),
                    )
                }
                if (error != null) {
                    Text(error!!, color = MaterialTheme.colorScheme.error,
                         style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = ::submit, enabled = !busy) {
                Text(if (isSetup) "Create" else "Unlock")
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel) { Text("Cancel") }
        },
    )
}
