package com.aishop.assistant.shops

import android.net.Uri

data class Shop(
    val id: String,
    val displayName: String,
    val emoji: String,
    val searchUrl: (query: String, maxPrice: Double?) -> String
)

object ShopRegistry {

    private fun enc(s: String) = Uri.encode(s)

    val all: List<Shop> = listOf(
        Shop("allegro", "Allegro", "🛒") { q, max ->
            val price = max?.let { "&price_to=${it.toInt()}" } ?: ""
            "https://allegro.pl/listing?string=${enc(q)}$price"
        },
        Shop("olx", "OLX", "📦") { q, max ->
            val price = max?.let { "&search%5Bfilter_float_price%3Ato%5D=${it.toInt()}" } ?: ""
            "https://www.olx.pl/oferty/q-${enc(q.replace(' ', '-'))}/$price"
        },
        Shop("ceneo", "Ceneo", "💸") { q, max ->
            val price = max?.let { ";0020-${it.toInt()}00" } ?: ""
            "https://www.ceneo.pl/szukaj-${enc(q)}$price"
        },
        Shop("xkom", "x-kom", "💻") { q, max ->
            val price = max?.let { "?f%5Bcenadosc%5D=${it.toInt()}" } ?: ""
            "https://www.x-kom.pl/szukaj?q=${enc(q)}${price.removePrefix("?").let { if (it.isEmpty()) "" else "&$it" }}"
        },
        Shop("mediaexpert", "Media Expert", "📺") { q, _ ->
            "https://www.mediaexpert.pl/search?query%5Bmenu_item%5D=&query%5Bquerystring%5D=${enc(q)}"
        },
        Shop("morele", "Morele", "🧩") { q, max ->
            val price = max?.let { "?priceTo=${it.toInt()}" } ?: ""
            "https://www.morele.net/wyszukiwarka/$price&q=${enc(q)}".replace("?&", "?")
        },
        Shop("empik", "Empik", "📚") { q, _ ->
            "https://www.empik.com/szukaj/produkt?q=${enc(q)}"
        },
        Shop("zalando", "Zalando", "👟") { q, _ ->
            "https://www.zalando.pl/katalog/?q=${enc(q)}"
        },
        Shop("google", "Google Shopping", "🔎") { q, max ->
            val price = max?.let { ",price:1,ppr_max:${it.toInt()}" } ?: ""
            "https://www.google.com/search?tbm=shop&q=${enc(q)}&tbs=mr:1$price"
        }
    )

    fun byIds(ids: List<String>): List<Shop> =
        if (ids.isEmpty()) all else all.filter { it.id in ids.map(String::lowercase) }
}
