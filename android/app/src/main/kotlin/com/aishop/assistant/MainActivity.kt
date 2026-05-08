package com.aishop.assistant

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aishop.assistant.ai.GeminiClient
import com.aishop.assistant.ai.ParsedIntent
import com.aishop.assistant.control.ActionExecutor
import com.aishop.assistant.control.PhoneControlService
import com.aishop.assistant.prefs.AppPrefs
import com.aishop.assistant.shops.PriceComparator
import com.aishop.assistant.shops.PriceOffer
import com.aishop.assistant.shops.ShopRegistry
import com.aishop.assistant.voice.VoiceRecognizer
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var voice: VoiceRecognizer
    private lateinit var prefs: AppPrefs
    private lateinit var executor: ActionExecutor

    private val micPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* user granted or not — start() i tak zwróci błąd jeśli nie */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        voice = VoiceRecognizer(this)
        prefs = AppPrefs(this)
        executor = ActionExecutor(this)

        setContent {
            MaterialTheme(colorScheme = darkAishopColors()) {
                AppRoot(
                    voice = voice,
                    prefs = prefs,
                    executor = executor,
                    onAskMicPermission = { micPermission.launch(Manifest.permission.RECORD_AUDIO) },
                    hasMicPermission = {
                        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
                                PackageManager.PERMISSION_GRANTED
                    }
                )
            }
        }
    }
}

private fun darkAishopColors() = darkColorScheme(
    primary = Color(0xFF8B5CF6),
    secondary = Color(0xFFEC4899),
    tertiary = Color(0xFF06B6D4),
    background = Color(0xFF07070F),
    surface = Color(0xFF12121E),
    surfaceVariant = Color(0xFF1E1E30),
    onPrimary = Color.White,
    onBackground = Color(0xFFF0EFFF),
    onSurface = Color(0xFFF0EFFF)
)

private sealed class ChatMsg {
    data class User(val text: String) : ChatMsg()
    data class Assistant(val text: String) : ChatMsg()
    data class Offers(val list: List<PriceOffer>) : ChatMsg()
    data class ShopLinks(val query: String, val shopIds: List<String>, val maxPrice: Double?) : ChatMsg()
}

@Composable
private fun AppRoot(
    voice: VoiceRecognizer,
    prefs: AppPrefs,
    executor: ActionExecutor,
    onAskMicPermission: () -> Unit,
    hasMicPermission: () -> Boolean
) {
    val scope = rememberCoroutineScope()
    var prompt by remember { mutableStateOf("") }
    var listening by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(prefs.geminiKey.isBlank()) }
    val messages = remember { mutableStateListOf<ChatMsg>() }

    Scaffold(
        topBar = { TopBar(onSettings = { showSettings = true }) },
        containerColor = Color(0xFF07070F)
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize()) {
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                if (messages.isEmpty()) item { EmptyState() }
                items(messages) { msg ->
                    when (msg) {
                        is ChatMsg.User -> Bubble(msg.text, mine = true)
                        is ChatMsg.Assistant -> Bubble(msg.text, mine = false)
                        is ChatMsg.Offers -> OffersCard(msg.list, executor)
                        is ChatMsg.ShopLinks -> ShopLinksCard(msg.query, msg.shopIds, msg.maxPrice, executor)
                    }
                    Spacer(Modifier.height(8.dp))
                }
                if (busy) item { TypingIndicator() }
            }

            InputBar(
                value = prompt,
                onValueChange = { prompt = it },
                listening = listening,
                onMic = {
                    if (!hasMicPermission()) { onAskMicPermission(); return@InputBar }
                    if (listening) { voice.stop(); listening = false; return@InputBar }
                    listening = true
                    voice.start(
                        onPartial = { prompt = it },
                        onResult = { text ->
                            listening = false
                            prompt = text
                            if (text.isNotBlank()) submit(text, prefs, executor, messages, scope) { busy = it; prompt = "" }
                        },
                        onError = { err ->
                            listening = false
                            messages += ChatMsg.Assistant("🎙️ $err")
                        }
                    )
                },
                onSend = {
                    val p = prompt.trim()
                    if (p.isNotBlank()) submit(p, prefs, executor, messages, scope) { busy = it; prompt = "" }
                }
            )
        }
    }

    if (showSettings) SettingsDialog(prefs, onClose = { showSettings = false }, onOpenA11y = { executor.openAccessibilitySettings() })
}

private fun submit(
    promptText: String,
    prefs: AppPrefs,
    executor: ActionExecutor,
    messages: androidx.compose.runtime.snapshots.SnapshotStateList<ChatMsg>,
    scope: kotlinx.coroutines.CoroutineScope,
    setBusy: (Boolean) -> Unit
) {
    messages += ChatMsg.User(promptText)
    val key = prefs.geminiKey
    if (key.isBlank()) {
        messages += ChatMsg.Assistant("Wpisz klucz Gemini API w Ustawieniach (ikona zębatki). Bezpłatny klucz: aistudio.google.com")
        return
    }
    setBusy(true)
    scope.launch {
        runCatching {
            val intent = GeminiClient(key).parsePrompt(promptText)
            handleIntent(intent, executor, messages)
        }.onFailure { messages += ChatMsg.Assistant("Błąd AI: ${it.message}") }
        setBusy(false)
    }
}

private suspend fun handleIntent(
    intent: ParsedIntent,
    executor: ActionExecutor,
    messages: androidx.compose.runtime.snapshots.SnapshotStateList<ChatMsg>
) {
    when (intent.type.uppercase()) {
        "ANSWER" -> messages += ChatMsg.Assistant(intent.answer ?: "Ok.")

        "OPEN_APP" -> {
            val name = intent.appName ?: intent.query.orEmpty()
            executor.launchApp(name)
            messages += ChatMsg.Assistant("Otwieram $name…")
        }

        "WEB_SEARCH" -> {
            val q = intent.query.orEmpty()
            executor.openUrl("https://www.google.com/search?q=${java.net.URLEncoder.encode(q, "UTF-8")}")
            messages += ChatMsg.Assistant("Szukam w Google: $q")
        }

        "PHONE_CONTROL" -> {
            messages += ChatMsg.Assistant("Wykonuję na telefonie…")
            val status = executor.runSteps(intent.steps)
            messages += ChatMsg.Assistant(status)
        }

        "SEARCH_SHOPS" -> {
            val q = intent.query ?: return run {
                messages += ChatMsg.Assistant("Nie wiem czego szukać — sprecyzuj.")
            }
            messages += ChatMsg.Assistant("Szukam: $q${intent.maxPrice?.let { " (do ${it.toInt()} zł)" } ?: ""}")
            messages += ChatMsg.ShopLinks(q, intent.shops, intent.maxPrice)
            runCatching {
                val offers = PriceComparator().compare(q, intent.maxPrice)
                if (offers.isNotEmpty()) messages += ChatMsg.Offers(offers)
            }
        }

        else -> messages += ChatMsg.Assistant(intent.answer ?: "Nie zrozumiałem.")
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TopBar(onSettings: () -> Unit) {
    val a11yOn = PhoneControlService.isEnabled()
    TopAppBar(
        title = {
            Column {
                Text("AI Shop", fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Text(
                    if (a11yOn) "Sterowanie telefonem: ON" else "Sterowanie telefonem: OFF",
                    fontSize = 11.sp,
                    color = if (a11yOn) Color(0xFF22C55E) else Color(0xFFF59E0B)
                )
            }
        },
        actions = {
            IconButton(onClick = onSettings) { Icon(Icons.Default.Settings, null) }
        },
        colors = TopAppBarDefaults.topAppBarColors(containerColor = Color(0xFF07070F))
    )
}

@Composable
private fun EmptyState() {
    Box(Modifier.fillMaxWidth().padding(top = 80.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("🛍️", fontSize = 56.sp)
            Spacer(Modifier.height(12.dp))
            Text("Powiedz albo napisz czego szukasz", fontSize = 16.sp, color = Color(0xFFA0A0C0))
            Spacer(Modifier.height(4.dp))
            Text(
                "np. „znajdź czarne buty Nike rozmiar 42 do 300 zł” albo „otwórz YouTube”",
                fontSize = 12.sp, color = Color(0xFF606080)
            )
        }
    }
}

@Composable
private fun Bubble(text: String, mine: Boolean) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start
    ) {
        Surface(
            shape = RoundedCornerShape(16.dp),
            color = if (mine) Color(0xFF8B5CF6) else Color(0xFF1E1E30),
            modifier = Modifier.widthIn(max = 320.dp)
        ) {
            Text(
                text,
                Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                color = Color.White, fontSize = 14.sp
            )
        }
    }
}

@Composable
private fun TypingIndicator() {
    Row(Modifier.padding(start = 8.dp)) {
        Surface(shape = RoundedCornerShape(16.dp), color = Color(0xFF1E1E30)) {
            Text("…myślę", Modifier.padding(horizontal = 14.dp, vertical = 10.dp), color = Color(0xFFA0A0C0))
        }
    }
}

@Composable
private fun OffersCard(offers: List<PriceOffer>, executor: ActionExecutor) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFF12121E),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.padding(12.dp)) {
            Text("Najlepsze oferty", fontWeight = FontWeight.SemiBold, color = Color.White)
            Spacer(Modifier.height(8.dp))
            offers.forEach { o ->
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFF1E1E30),
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                ) {
                    Column(Modifier.padding(10.dp)) {
                        Text(o.title, color = Color.White, fontSize = 13.sp, maxLines = 2)
                        Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(o.price, color = Color(0xFFEC4899), fontWeight = FontWeight.Bold)
                            Spacer(Modifier.weight(1f))
                            Text(o.source, color = Color(0xFF606080), fontSize = 11.sp)
                            Spacer(Modifier.width(8.dp))
                            TextButton(onClick = { executor.openUrl(o.url) }) { Text("Otwórz") }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ShopLinksCard(query: String, shopIds: List<String>, maxPrice: Double?, executor: ActionExecutor) {
    val shops = ShopRegistry.byIds(shopIds)
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFF12121E),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.padding(12.dp)) {
            Text("Otwórz w sklepach", fontWeight = FontWeight.SemiBold, color = Color.White)
            Spacer(Modifier.height(8.dp))
            shops.chunked(2).forEach { row ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    row.forEach { shop ->
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = Color(0xFF1E1E30),
                            modifier = Modifier.weight(1f)
                        ) {
                            Row(
                                Modifier.fillMaxWidth().padding(10.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(shop.emoji, fontSize = 18.sp)
                                Spacer(Modifier.width(8.dp))
                                Text(shop.displayName, color = Color.White, fontSize = 13.sp, modifier = Modifier.weight(1f))
                                TextButton(onClick = { executor.openUrl(shop.searchUrl(query, maxPrice)) }) { Text("Idź") }
                            }
                        }
                    }
                    if (row.size == 1) Spacer(Modifier.weight(1f))
                }
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun InputBar(
    value: String,
    onValueChange: (String) -> Unit,
    listening: Boolean,
    onMic: () -> Unit,
    onSend: () -> Unit
) {
    Surface(color = Color(0xFF12121E), shadowElevation = 8.dp) {
        Row(
            Modifier.fillMaxWidth().padding(10.dp).navigationBarsPadding(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            FilledTonalIconButton(
                onClick = onMic,
                colors = IconButtonDefaults.filledTonalIconButtonColors(
                    containerColor = if (listening) Color(0xFFEC4899) else Color(0xFF1E1E30)
                )
            ) { Icon(Icons.Default.Mic, contentDescription = "Mów", tint = Color.White) }

            Spacer(Modifier.width(8.dp))

            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("Wpisz lub powiedz…", color = Color(0xFF606080)) },
                singleLine = false,
                maxLines = 4,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    focusedBorderColor = Color(0xFF8B5CF6),
                    unfocusedBorderColor = Color(0xFF1E1E30)
                )
            )

            Spacer(Modifier.width(8.dp))

            FilledIconButton(
                onClick = onSend,
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = Color(0xFF8B5CF6))
            ) { Icon(Icons.Default.Send, contentDescription = "Wyślij", tint = Color.White) }
        }
    }
}

@Composable
private fun SettingsDialog(prefs: AppPrefs, onClose: () -> Unit, onOpenA11y: () -> Unit) {
    var key by remember { mutableStateOf(prefs.geminiKey) }
    AlertDialog(
        onDismissRequest = onClose,
        confirmButton = {
            TextButton(onClick = { prefs.geminiKey = key.trim(); onClose() }) { Text("Zapisz") }
        },
        dismissButton = { TextButton(onClick = onClose) { Text("Anuluj") } },
        title = { Text("Ustawienia") },
        text = {
            Column {
                Text("Klucz Gemini API (darmowy z aistudio.google.com)", fontSize = 13.sp)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = key,
                    onValueChange = { key = it },
                    placeholder = { Text("AIza…") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(16.dp))
                Text("Sterowanie telefonem", fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                Text(
                    "Aby AI mogło klikać i wpisywać w innych aplikacjach, włącz 'AI Shop' w Ustawieniach Dostępności.",
                    fontSize = 12.sp, color = Color(0xFFA0A0C0)
                )
                Spacer(Modifier.height(8.dp))
                FilledTonalButton(onClick = onOpenA11y) { Text("Otwórz Ustawienia Dostępności") }
            }
        }
    )
}
