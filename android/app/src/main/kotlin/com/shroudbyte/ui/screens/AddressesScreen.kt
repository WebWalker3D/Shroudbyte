package com.shroudbyte.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.shroudbyte.ShroudApplication
import com.shroudbyte.addresses.Address

private val FIELD_LABELS = listOf(
    "name"            to "Full name",
    "given-name"      to "Given (first) name",
    "family-name"     to "Family (last) name",
    "organization"    to "Organization",
    "street-address"  to "Street address",
    "address-line2"   to "Address line 2",
    "address-level2"  to "City",
    "address-level1"  to "State / region",
    "postal-code"     to "Postal / ZIP",
    "country"         to "Country code",
    "email"           to "Email",
    "tel"             to "Phone",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddressesScreen(
    app: ShroudApplication,
    onBack: () -> Unit,
    onFill: (String) -> Unit,
) {
    var entries by remember { mutableStateOf(app.addresses.list()) }
    var editing by remember { mutableStateOf<Address?>(null) }
    var creating by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Addresses") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Back")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { creating = true }) {
                Icon(Icons.Default.Add, contentDescription = "Add address")
            }
        },
    ) { padding ->
        if (entries.isEmpty()) {
            EmptyState(text = "No saved addresses", modifier = Modifier.padding(padding))
        } else {
            LazyColumn(modifier = Modifier.padding(padding).fillMaxSize()) {
                items(entries, key = { it.id }) { addr ->
                    AddressRow(
                        addr = addr,
                        onFill = { onFill(addr.id) },
                        onEdit = { editing = addr },
                        onDelete = {
                            app.addresses.remove(addr.id)
                            entries = app.addresses.list()
                        },
                    )
                    HorizontalDivider()
                }
            }
        }
    }

    if (creating) {
        AddressEditorDialog(
            initial = null,
            onCancel = { creating = false },
            onSave = { label, fields ->
                app.addresses.add(label, fields)
                entries = app.addresses.list()
                creating = false
            },
        )
    }
    editing?.let { addr ->
        AddressEditorDialog(
            initial = addr,
            onCancel = { editing = null },
            onSave = { label, fields ->
                app.addresses.update(addr.id, label = label, fields = fields)
                entries = app.addresses.list()
                editing = null
            },
        )
    }
}

@Composable
private fun AddressRow(
    addr: Address,
    onFill: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onFill)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(addr.label, style = MaterialTheme.typography.bodyLarge)
            val summary = listOfNotNull(
                addr.fields["name"],
                addr.fields["street-address"],
            ).joinToString(" · ")
            if (summary.isNotEmpty()) {
                Text(summary, style = MaterialTheme.typography.bodySmall,
                     color = MaterialTheme.colorScheme.outline)
            }
        }
        IconButton(onClick = onEdit) {
            Icon(Icons.Default.Edit, contentDescription = "Edit")
        }
        IconButton(onClick = onDelete) {
            Icon(Icons.Default.Delete, contentDescription = "Delete")
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddressEditorDialog(
    initial: Address?,
    onCancel: () -> Unit,
    onSave: (String, Map<String, String>) -> Unit,
) {
    var label by remember { mutableStateOf(initial?.label.orEmpty()) }
    val values = remember {
        FIELD_LABELS.associate { (k, _) -> k to mutableStateOf(initial?.fields?.get(k).orEmpty()) }
    }

    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text(if (initial == null) "New address" else "Edit address") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 480.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = label,
                    onValueChange = { label = it },
                    label = { Text("Label (Home, Work, ...)") },
                    singleLine = true,
                )
                androidx.compose.foundation.lazy.LazyColumn(
                    modifier = Modifier.weight(1f, fill = false),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(FIELD_LABELS) { (key, prettyLabel) ->
                        val state = values.getValue(key)
                        OutlinedTextField(
                            value = state.value,
                            onValueChange = { state.value = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text(prettyLabel) },
                            placeholder = { Text(key) },
                            singleLine = true,
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val fields = values
                    .mapValues { it.value.value }
                    .filterValues { it.isNotBlank() }
                onSave(label, fields)
            }) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onCancel) { Text("Cancel") }
        },
    )
}
