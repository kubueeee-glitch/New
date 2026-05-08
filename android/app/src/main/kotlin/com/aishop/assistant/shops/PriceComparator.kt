package com.aishop.assistant.shops

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.jsoup.Jsoup

data class PriceOffer(
    val source: String,
    val title: String,
    val price: String,
    val url: String
)

/**
 * Pobiera oferty z Ceneo i Google Shopping (HTML scraping).
 * Działa od strony Androida — brak CORS. Selektory mogą się zmieniać; w razie braku wyników
 * apka i tak pokaże linki "otwórz w sklepie".
 */
class PriceComparator {

    suspend fun compare(query: String, maxPrice: Double?): List<PriceOffer> = coroutineScope {
        val ceneo = async(Dispatchers.IO) { runCatching { fetchCeneo(query, maxPrice) }.getOrDefault(emptyList()) }
        val google = async(Dispatchers.IO) { runCatching { fetchGoogleShopping(query, maxPrice) }.getOrDefault(emptyList()) }
        (ceneo.await() + google.await()).take(20)
    }

    private fun fetchCeneo(query: String, maxPrice: Double?): List<PriceOffer> {
        val priceFrag = maxPrice?.let { ";0020-${it.toInt()}00" } ?: ""
        val url = "https://www.ceneo.pl/szukaj-${java.net.URLEncoder.encode(query, "UTF-8")}$priceFrag"
        val doc = Jsoup.connect(url)
            .userAgent("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile")
            .timeout(15_000)
            .get()
        return doc.select(".cat-prod-row").take(10).mapNotNull { row ->
            val title = row.selectFirst(".cat-prod-row__name a, .go-to-product")?.text().orEmpty()
            val price = row.selectFirst(".price")?.text()?.trim().orEmpty()
            val href = row.selectFirst(".cat-prod-row__name a, .go-to-product")?.attr("href").orEmpty()
            if (title.isBlank() || price.isBlank()) null else PriceOffer(
                source = "Ceneo",
                title = title,
                price = price,
                url = if (href.startsWith("http")) href else "https://www.ceneo.pl$href"
            )
        }
    }

    private fun fetchGoogleShopping(query: String, maxPrice: Double?): List<PriceOffer> {
        val priceFrag = maxPrice?.let { ",price:1,ppr_max:${it.toInt()}" } ?: ""
        val url = "https://www.google.com/search?tbm=shop&q=${java.net.URLEncoder.encode(query, "UTF-8")}&tbs=mr:1$priceFrag"
        val doc = Jsoup.connect(url)
            .userAgent("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile")
            .header("Accept-Language", "pl-PL,pl;q=0.9")
            .timeout(15_000)
            .get()
        return doc.select("div.sh-dgr__content, div.sh-dlr__list-result").take(10).mapNotNull { card ->
            val title = card.selectFirst("h3, h4")?.text().orEmpty()
            val price = card.selectFirst("span.a8Pemb, .kHxwFf, .Pgbknd")?.text().orEmpty()
            val href = card.selectFirst("a")?.attr("href").orEmpty()
            if (title.isBlank() || price.isBlank() || href.isBlank()) null else PriceOffer(
                source = "Google Shopping",
                title = title,
                price = price,
                url = if (href.startsWith("http")) href else "https://www.google.com$href"
            )
        }
    }
}
