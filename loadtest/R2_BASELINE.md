# Média před R2 — naměřená baseline

Tenhle soubor existuje kvůli jedné otázce: **o kolik pomůže přesun médií na
Cloudflare R2?** Aby na to šlo odpovědět číslem a ne dojmem, je tady stav *před*
migrací a přesný postup, jak naměřit stav *po* ní.

Měřeno: **3. 8. 2026, 23:5x**, proti `https://www.gameofyolo.com` (živý provoz).
Nástroj: [run_prod_ramp.py](run_prod_ramp.py) + [locustfile_prod.py](locustfile_prod.py).
Surová data: [results/before-r2/](results/before-r2/) (`summary.json` + locust CSV).

---

## Jak to zopakovat po R2

```bash
cd loadtest
/usr/bin/python3 run_prod_ramp.py --label after-r2      # stejné kroky, stejná délka
/usr/bin/python3 run_prod_ramp.py --compare before-r2 after-r2
```

Parametry **neměň** — kroky (3/6/12/24 uživatelů), 20 s na krok a rychlost API
probe jsou zadrátované v defaultech přesně proto, aby se dvě měření dala položit
vedle sebe. Když je změníš, srovnání ztratí smysl a musíš přeměřit i „před".

Jedna věc, kterou ovlivnit nemůžeš: měří se z jedné linky a v jednu denní dobu.
Pusť „po" ideálně ve stejnou noční hodinu, ať do toho nemluví reálný provoz.

---

## Co se měří a proč zrovna to

Média dnes servíruje Django (`mysite/urls.py` → `django.views.static.serve`), což
znamená, že **gunicorn worker je obsazený po celou dobu přenosu souboru**. Otázka
tedy není „kolik obrázků za sekundu" — ale **co dělá stahování obrázků s API,
které běží vedle nich**.

Proto každý krok pouští `MediaUser` (škáluje se) a vedle nich přesně jednoho
`ApiProbeUser` (~1 req/s), a report je drží oddělené. Číslo, které rozhoduje o
R2, je sloupec **API p95**.

Všechny URL mají náhodný `_cb=` parametr, takže Cloudflare vrací `MISS` a request
opravdu dojde na origin. Bez toho by se měřil edge cache, ne aplikace.

---

## Baseline: PŘED R2

| Media uživatelů | Média rps | Média p95 | Média max | **API p95** | API p50 (`/events`) | Chyby |
|---|---|---|---|---|---|---|
| 3  | 1,6  | 160 ms | 202 ms | 180 ms | 92 ms | 0 |
| 6  | 2,6  | 190 ms | 274 ms | 170 ms | 120 ms | 0 |
| 12 | 5,4  | 210 ms | 307 ms | 230 ms | 110 ms | 0 |
| 24 | 10,0 | 320 ms | **6 707 ms** | **990 ms** | 190 ms | 0 |

Celkem přeneseno 366 MB za běh (to je placený egress z Renderu — proto má skript
strop `--max-mb 400`).

**Jak to číst:** do 12 souběžných stahování se nic zvláštního neděje. Při 24 se
API p95 zhorší z ~180 ms na **990 ms** a jeden požadavek na obrázek trval
**6,7 sekundy**. Žádná 5xx, takže se nic nerozbilo — ale je vidět fronta, přesně
jak se čeká od modelu „worker drží soubor".

⚠ **Saturace nedosaženo.** Ramp skončil na 24 uživatelích kvůli stropu na
přenesená data, ne proto, že by server přestal stíhat. Skutečný strop je někde
výš a tohle měření ho nenašlo — říká „takhle to vypadá při 24 souběžných
stahováních", ne „tady je konec".

---

## Kontext naměřený u toho (platí i bez R2)

**Per-IP strop API je přesně 120 req/min.** `DEFAULT_THROTTLE_RATES['anon']`.
Sekvenčně měřeno: 429 přišla po **120.** requestu, s `Retry-After: 43`. Souběžně
z 10 vláken jich projde ~140, protože se workery při zápisu do počítadla
předhánějí. Limituje **Django, ne Cloudflare** — 429 má české JSON tělo z
`mysite/drf.py:api_exception_handler`; edge pravidlo na `/api/*` zatím nemáš.

Pro jednoho návštěvníka je to štědré (jedno načtení stránky je pár requestů), ale
**celkovou kapacitu API z jednoho stroje takhle změřit nejde** — narazíš na
vlastní throttle dřív než na server. Postup, jak to obejít, je níž.

**Klientská linka není úzké hrdlo.** 386 Mbit/s (48 MB/s) změřeno proti
`speed.cloudflare.com`; ramp vytáhl maximálně 8,6 MB/s, tedy ~18 % linky.
Naměřené hodnoty jsou tedy o serveru, ne o mém internetu.

**Průměrný obrázek má ~931 kB, největší 6,3 MB na disku** (52 souborů). Na web je
to hodně — a je to i důvod, proč se fronta objeví už při 24 uživatelích.

**`.mobile.webp` varianty u event_logos chybí** — `HEAD` na ně vrací 404.
WebP pipeline (`image_utils.make_webp_variant`) je zjevně nedoběhla nebo se na
loga nevztahuje. Stojí za kontrolu **nezávisle na R2**: zmenšit 900kB PNG na
WebP je levnější a účinnější než cokoli, co udělá jiné úložiště.

### Cloudflare média cachuje — ověřeno, ne odhadnuto

25 z 25 obrázků stažených **bez** cache-busteru vrátilo `cf-cache-status: HIT`,
tedy Cloudflare je obsloužil z edge a na Render vůbec nešly. Že to nenahřály moje
vlastní testy, je vidět na hlavičce `age`: **medián 23 hodin, maximum 88 hodin** —
ty objekty ležely na edge dávno před tímhle měřením (ramp navíc používá `_cb=`,
což je jiný cache key). Origin k tomu posílá `cache-control: public,
max-age=2592000`, tedy 30 dní.

Ověřit si to můžeš jednou řádkou:

```bash
curl -sI https://www.gameofyolo.com/media/event_images/<soubor>.jpg \
  | grep -iE "cf-cache-status|age:|cache-control"
```

**Platnost tohohle zjištění má hranici:** `HIT` je vždy jen pro *ten* PoP, který
request obsloužil (u mě Praha) a v *ten* okamžik. Návštěvník ze zahraničí trefí
jiný PoP s vlastní cache a málo prohlížené obrázky z edge vypadnou. Pro české
publikum na české doméně to zobecnit lze, pro dlouhý ocas obrázků ne úplně.

### Cloudflare Polish je zapnutý

Vypadlo to z hlavičky `cf-polished: ok, orig_size=…`, kterou Cloudflare posílá u
každého obrázku. Znamená to, že obrázky na edge překomprimovává, takže **origin a
návštěvník nevidí stejné bajty**:

| | velikost |
|---|---|
| co leží na Renderu (25 souborů) | 28,8 MB |
| co reálně dostane návštěvník | 24,7 MB |

Úspora **14 % v průměru**, u velkého JPEGu (`Lysa_hora-113.jpg`) 32 % — 6,3 MB na
disku → 4,3 MB po drátě. U průhledných PNG jen ~7 %, u jednoho souboru Polish
vzdal (`webp_bigger`).

Praktický důsledek pro měření: **velikosti souborů měřené přes Cloudflare jsou
polished, ne originální.** Když budeš porovnávat objem dat, ber čísla z Renderu
nebo z `orig_size` v té hlavičce, ne z `content-length`.

---

## Měření kapacity API (`--mode api`)

Tenhle běh je **něco jiného než ten výš**: neptá se na média, ptá se, kolik
requestů API uveze. Bez zvednutí throttlu je ale k ničemu — po 120 requestech za
minutu měří rate limiter, ne server.

Rychlosti jsou proto přepínatelné přes env (`mysite/settings.py`, `_throttle_rate`).
Postup celý, včetně vrácení zpět:

1. **Render → Environment**, přidej:

   ```
   ANON_THROTTLE_RATE=off
   ```

   (nebo konkrétní číslo, `ANON_THROTTLE_RATE=6000/min`). Render službu restartuje,
   počkej, až je deploy zelený.

2. **Spusť ramp.** Trvá ~2 minuty, kroky 10/25/50/100/200 uživatelů:

   ```bash
   cd loadtest
   /usr/bin/python3 run_prod_ramp.py --mode api --label api-baseline
   ```

3. **Vrať to zpátky.** Smaž tu proměnnou (nebo `ANON_THROTTLE_RATE=120/min`) a
   nech službu restartovat.

   ⚠ Dokud je limit zvednutý, je zvednutý **pro celý internet**, ne jen pro
   tvůj test. Je to okno, ve kterém ti kdokoli může scrapovat API bez omezení.
   Proto to pusť v noci a vrať hned, ne „až se k tomu dostanu". Auth endpointy
   (login/registrace/reset hesla) env knob **nemají** schválně — to je
   bezpečnostní pojistka, ne ladicí parametr.

Ramp se sám zastaví na první 5xx a u každého kroku hlásí, kolik requestů bylo
odmítnuto throttlem — když vidíš „measured the rate limiter", proměnná se
nepropsala.

**Co čekat:** gunicorn běží se 2 workery × 2 vlákna
([gunicorn.conf.py](../djangotutorial/gunicorn.conf.py)), tedy **4 souběžné
requesty**. Přes tenhle strop se nedostaneš ať pošleš cokoli; při 100+
uživatelích poroste fronta a p95 s ní. To není chyba, to je ta kapacita — a
`WEB_CONCURRENCY` je páka, kterou se dá zvednout, pokud na to je RAM.

---

## Co od R2 čekat (a co ne)

Realisticky se zlepší tohle:

1. **API p95 pod zátěží médií** — worker se přestane blokovat přenosem souboru.
   Řádek „24 uživatelů" by měl spadnout z ~990 ms zpátky k ~180 ms. Tohle je ten
   hlavní důvod migrace a tabulka výš je přesně na to.
2. **Egress a disk na Renderu** — soubory přestanou téct přes dyno.
3. **Cache MISS** — po R2 obsluhuje minutí edge cache R2, ne gunicorn.

Co se **nezlepší** a nemá cenu to od R2 čekat:

- **Běžný návštěvník to nejspíš nepozná.** Cloudflare média drží 30 dní a u všech
  25 zkoušených souborů vrátil `HIT` (viz doklad výš), takže na origin dnes
  chodí hlavně minutí cache. Zlepší se chování při MISS a chování API vedle
  něj — ne typická návštěva zahřátého obrázku.
- **Velikost souborů.** 6MB JPEG bude 6MB JPEG i na R2 (Polish z něj i tam udělá
  ~4 MB, ten běží nezávisle na úložišti). Tohle řeší WebP varianty, ne úložiště.

Takže pokud po migraci uvidíš v tabulce „24 uživatelů" API p95 kolem 200 ms
místo 990 ms, R2 udělalo přesně to, kvůli čemu se nasazovalo. Když se nezmění
nic, byla úzkým hrdlem jiná věc a stojí za to hledat dál (počet workerů,
Postgres, velikost obrázků).

---

## Poznámky k metodice

- Test běží proti **živému webu**. Ramp se zastaví na první 5xx a má strop na
  přenesená data. Přesto ho nepouštěj ve špičce.
- p95 API probe stojí na ~6–8 vzorcích na endpoint a krok. Trend napříč kroky je
  konzistentní, ale jedno číslo samo o sobě nepřeceňuj — proto se porovnává celý
  sloupec, ne jedna buňka.
- `results/<label>/` obsahuje i původní locust CSV, kdyby ses chtěl dívat na
  distribuci sám.
