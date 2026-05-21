package com.shroudbyte.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.shroudbyte.ShroudApplication
import com.shroudbyte.passwords.PasswordEntry

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PasswordsScreen(
    app: ShroudApplication,
    onBack: () -> Unit,
) {
    val vault = app.vault

    // Gate the screen on vault state: locked → unlock/setup dialog;
    // unlocked → manager UI. Closing the dialog returns to the browser.
    var unlocked by remember { mutableStateOf(vault.isUnlocked) }
    if (!unlocked) {
        VaultDialog(
            vault = vault,
            onCancel = onBack,
            onUnlocked = { unlocked = true },
        )
        return
    }

    var entries by remember { mutableStateOf(vault.all()) }
    var editing by remember { mutableStateOf<PasswordEntry?>(null) }
    var creating by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Passwords (${entries.size})") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = {
                        vault.lock()
                        unlocked = false
                    }) {
                        Icon(Icons.Default.Lock, contentDescription = "Lock vault")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { creating = true }) {
                Icon(Icons.Default.Add, contentDescription = "Add credential")
            }
        },
    ) { padding ->
        if (entries.isEmpty()) {
            EmptyState(text = "No saved credentials yet",
                       modifier = Modifier.padding(padding))
        } else {
            LazyColumn(modifier = Modifier.padding(padding).fillMaxSize()) {
                items(entries, key = { it.id }) { e ->
                    PasswordRow(
                        entry = e,
                        onEdit = { editing = e },
                        onDelete = {
                            vault.remove(e.id)
                            entries = vault.all()
                        },
                    )
                    HorizontalDivider()
                }
            }
        }
    }

    if (creating) {
        PasswordEditor(
            initial = null,
            onCancel = { creating = false },
            onSave = { site, user, pass, name ->
                vault.add(site, user, pass, name)
                entries = vault.all()
                creating = false
            },
        )
    }
    editing?.let { e ->
        PasswordEditor(
            initial = e,
            onCancel = { editing = null },
            onSave = { _, user, pass, name ->
                vault.update(e.id, username = user, password = pass, name = name)
                entries = vault.all()
                editing = null
            },
        )
    }
}

@Composable
private fun PasswordRow(
    entry: PasswordEntry,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onEdit)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = entry.name.ifBlank { entry.siteUrl },
                style = MaterialTheme.typography.bodyLarge,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = entry.username,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.outline,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
        }
        IconButton(onClick = onDelete) {
            Icon(Icons.Default.Delete, contentDescription = "Delete")
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PasswordEditor(
    initial: PasswordEntry?,
    onCancel: () -> Unit,
    onSave: (site: String, username: String, password: String, name: String) -> Unit,
) {
    var site by remember { mutableStateOf(initial?.siteUrl.orEmpty()) }
    var username by remember { mutableStateOf(initial?.username.orEmpty()) }
    var password by remember { mutableStateOf(initial?.password.orEmpty()) }
    var name by remember { mutableStateOf(initial?.name.orEmpty()) }
    var visible by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text(if (initial == null) "New credential" else "Edit credential") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = site,
                    onValueChange = { site = it },
                    label = { Text("Site URL") },
                    singleLine = true,
                    readOnly = initial != null, // changing the URL re-keys lookups; keep it stable
                )
                OutlinedTextField(
                    value = username,
                    onValueChange = { username = it },
                    label = { Text("Username") },
                    singleLine = true,
                )
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password") },
                    singleLine = true,
                    visualTransformation = if (visible)
                        androidx.compose.ui.text.input.VisualTransformation.None
                    else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    trailingIcon = {
                        IconButton(onClick = { visible = !visible }) {
                            Icon(
                                if (visible) Icons.Default.Visibility else Icons.Default.VisibilityOff,
                                contentDescription = if (visible) "Hide" else "Show",
                            )
                        }
                    },
                )
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Label (optional)") },
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onSave(site.trim(), username.trim(), password, name.trim()) },
                enabled = site.isNotBlank() && username.isNotBlank() && password.isNotBlank(),
            ) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onCancel) { Text("Cancel") }
        },
    )
}
