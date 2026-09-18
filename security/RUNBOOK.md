# Runbook — kroky, které musíš udělat ty

Kód je hotový a otestovaný. Tenhle dokument pokrývá to, co zbývá a co nejde
udělat z repozitáře: nastavení v Cloudflare, Renderu a Google Cloud Console.

Každý krok má **ověření** — příkaz nebo klik, kterým potvrdíš, že to opravdu
funguje. Bez ověření krok neodškrtávej; většina těchhle věcí selhává tiše.

Pořadí je podle poměru přínos/práce. Krok 1 a 2 zvládneš za půl hodiny a
pokrývají většinu reálného rizika.

---

## 1. Cloudflare Access na admin ⏱ 15 min 🔴

**Proč:** Tohle je jediná změna, po které se nepřihlášený request k Djangu
vůbec nedostane — zastaví se na edgi. Boti, scannery a náhodné pokusy nemají
s čím komunikovat. Přesun adminu na tajnou cestu (krok 2) je jen úklid logů;
tohle je ta skutečná obrana.

1. Cloudflare dashboard → **Zero Trust** → Access → Applications → **Add an
   application** → *Self-hosted*
2. Application name: `GameOfYolo admin`
3. Session duration: 24 h
4. Public hostname: `gameofyolo.com`, Path: `sprava-x7k2` *(nebo cokoli, co
   nastavíš v kroku 2 — bez lomítka na začátku)*
5. Policy: Action **Allow** → Include → **Emails** → tvůj e-mail
6. Save

**Ověření:** V anonymním okně otevři `https://gameofyolo.com/sprava-x7k2/`.
Musí přijít přihlašovací obrazovka Cloudflare, **ne** Django login. Pokud vidíš
Django login, Access se neaplikoval — zkontroluj path.

> Free tier pokrývá 50 uživatelů. Pokud Access nechceš, chudší varianta je WAF
> rule omezená na tvoje IP — funguje, ale je otravná na mobilu.

---

## 2. Admin na jiné cestě ⏱ 5 min 🔴

**Proč:** Není to bezpečnost, je to čistota signálu. Každý bot na internetu
zkouší `/admin/`, takže ty řádky v logu nic neznamenají. Po přesunu plošný šum
zmizí a jediný pokus o přístup na tvou skutečnou admin URL je něco, co stojí za
přečtení.

Na Renderu → Environment → přidej:

```
ADMIN_URL=sprava-x7k2/
```

Zvol si vlastní náhodný řetězec, ne tenhle z dokumentace. Lomítko na konci
nech (kód ho doplní, ale ať je to explicitní).

**Ověření:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://gameofyolo.com/admin/
# 200 = SPA shell (správně: vypadá jako každá jiná neexistující adresa)

curl -s https://gameofyolo.com/robots.txt | grep -i admin
# nesmí vrátit NIC — jinak jsi tu cestu právě zveřejnil
```

> Kód se o `robots.txt` postará sám: jakmile `ADMIN_URL` není výchozí, řádek
> `Disallow: /admin/` zmizí. Nikdy tam tu novou cestu nepřidávej ručně —
> robots.txt je veřejný soubor, „Disallow" je zveřejněná adresa, ne skrytá.

Pro `X-Robots-Tag: noindex` na adminu: Cloudflare → Rules → **Transform Rules**
→ Modify Response Header → If `URI Path starts with /sprava-x7k2` → Set static
`X-Robots-Tag: noindex`.

---

## 3. Cloudflare cache rules 🔴

**Proč:** Tohle je jediné místo v celém plánu, kde ti optimalizace může vyrobit
únik dat. Když CDN uloží personalizovanou odpověď pod klíčem bez identity,
naservíruje ji dalšímu návštěvníkovi.

Rules → **Cache Rules**, v tomhle pořadí:

| # | Podmínka | Nastavení |
|---|---|---|
| 1 | URI Path starts with `/api/v1/auth` | **Bypass cache** |
| 2 | URI Path starts with `/accounts` | **Bypass cache** |
| 3 | URI Path starts with `/sprava-x7k2` | **Bypass cache** |
| 4 | URI Path starts with `/static/` | Cache Everything, Edge TTL 1 rok |
| 5 | Hostname equals `img.gameofyolo.com` | Cache Everything, Edge TTL 1 měsíc |

Backend už posílá `Cache-Control: no-store` na všech personalizovaných
endpointech (`/api/v1/auth/me/`, profily, hráči, seznam akcí, detail akce) —
tahle pravidla jsou druhá vrstva, ne jediná.

**Ověření 🔴 — tenhle test dělej vždycky:**

```bash
curl -I https://gameofyolo.com/api/v1/auth/me/
# Cache-Control: ... no-store ...
# cf-cache-status: BYPASS nebo DYNAMIC
```

A ruční verze, která odhalí i to, co curl nechytí: přihlas se jako uživatel A,
načti profil, pak **v anonymním okně** otevři stejnou URL. Nesmíš vidět data
uživatele A.

---

## 4. R2 pro média ✅ hotovo

Média se servírují z R2 přes `img.gameofyolo.com` (vlastní doména schválně —
SVG s vloženým skriptem by na hlavní doméně běžel v originu appky). Jakmile jsou
nastavené `MEDIA_S3_*` proměnné, je `MEDIA_S3_ENABLED` ve výchozím stavu zapnuté;
`0` má smysl jen při dalším cutoveru: URL se skládají za běhu podle aktivního
backendu, takže se **nejdřív kopíruje s vypnutým přepínačem, ověří, a teprve
pak přepíná** (`manage.py migrate_media_to_s3 --dry-run` → bez parametru →
`--verify`; příkaz nic nemaže a jde opakovat).

**Ověření:**

```bash
curl -I https://img.gameofyolo.com/event_images/<nejaky-soubor>.webp
# 200, při druhém volání cf-cache-status: HIT
```

Pošli odkaz na akci do WhatsAppu — náhledový obrázek se musí ukázat (link
preview čte obrázek přes storage API).

Zbývá:

- [ ] smazat obsah `MEDIA_ROOT` na disku Renderu a disk odpojit — až po ověření,
      že je v R2 všechno; do té doby je to jediná záloha
- [ ] Cloudflare → Speed → Optimization → **Polish** (WebP/AVIF podle `Accept`)

---

## 5. Google login ⏱ 20 min 🟡

Kód je hotový včetně obou kritických pojistek (žádné automatické spojování
účtů podle e-mailu, `is_staff=False` v adapteru). Chybí jen credentials.

1. [Google Cloud Console](https://console.cloud.google.com) → nový projekt
2. **OAuth consent screen** → External → název, support e-mail, doména
3. **Credentials** → Create credentials → OAuth client ID → *Web application*
4. Authorized redirect URI — **musí sedět na znak**:
   ```
   https://gameofyolo.com/accounts/google/login/callback/
   ```
   Včetně koncového lomítka. Pokud používáš i `www`, přidej i tu variantu.
5. Na Render:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```

**Dvě místa, kde se to typicky zasekne:**

- `redirect_uri_mismatch` → URI nesedí přesně (lomítko, `www`, http vs https)
- Callback odchází jako `http://` → chybí `SECURE_PROXY_SSL_HEADER`. To už
  v settings je, ale jen když `HTTPS` není `0` — na Renderu ho nenastavuj.

**Ověření:**

1. V anonymním okně → Přihlášení → *Pokračovat přes Google* → vytvoří se účet
2. V adminu zkontroluj, že ten uživatel má `is_staff = False` a má profil
   se zaznamenaným GDPR souhlasem
3. Zkus se přes Google přihlásit e-mailem, který už má heslový účet — **nesmí**
   se automaticky spojit. To je ta pojistka proti převzetí účtu.

---

## 6. Gunicorn a Postgres 🟡

Start command je `bash start.sh` (v `djangotutorial/`; spouští gunicorn s
`gunicorn.conf.py`). Workery a vlákna se nastavují proměnnými, ne parametry:

```
WEB_CONCURRENCY=2      # po přechodu na R2 se tři workery do 512 MB nevejdou
GUNICORN_THREADS=2
```

Rozpočet paměti je spočítaný v `gunicorn.conf.py`; před změnou ho přeměř
(`.venv/bin/python script/memory_budget.py`). Souběžných requestů je
`WEB_CONCURRENCY × GUNICORN_THREADS` a stejně tolik spojení do Postgresu
(`CONN_MAX_AGE` je 600 s) — zkontroluj limit instance.

---

## 7. CSP ⚪

CSP je **vynucená** ve výchozím stavu; inline skripty adminu řeší
`AdminCSPExemptMiddleware` jen pro admin cestu. Na nové doméně můžeš na týden
nastavit `CSP_REPORT_ONLY=1`, projít reporty v konzoli prohlížeče a proměnnou
zase smazat.

---

## 8. Rate limiting na edgi 🟡

Aplikační throttling (django-axes + DRF) už běží. Cloudflare vrstva je proti
objemu — to je jediná obrana, která funguje proti skutečnému DDoS, protože tvůj
origin ho jinak neustojí bez ohledu na kód.

⚠ **Limit na IP nechrání účet.** Ani DRF throttly, ani Cloudflare pravidla níž,
ani axes lockout na dvojici (IP, username) nezastaví útok rozprostřený přes stovky
IP na jeden účet — každá IP udělá dva pokusy a nikde nepřeteče. Proto běží druhá
vrstva: počítadlo neúspěšných pokusů na *username* přes všechny IP
(`ACCOUNT_FAILURE_LIMIT` v settings, implementace `accounts/axes_handler.py`).
Zámek účtu je sám o sobě páka na DoS, takže limit je vysoko (40/hod) a IP, ze které
se uživatel v posledních 30 dnech úspěšně přihlásil, má výjimku.

Security → **Rate limiting rules**:

| Cesta | Limit |
|---|---|
| `/api/v1/auth/login/` | 10 req / min / IP |
| `/api/v1/auth/register/` | 5 req / hod / IP |
| `/api/*` | 300 req / min / IP |

---

## 9. Odstranění telefonních čísel ✅ hotovo (migrace 0026)

Sloupec s telefony je pryč; identitou hráče v syncu je e-mail z formuláře, u
starších listů jméno (`tasks.resolve_player`). Co zůstává na tobě:

1. **V Google Forms u každého nového formuláře zapni „Shromažďovat e-mailové
   adresy" (Nastavení → Odpovědi).** Bez toho se hráči párují jen podle jména
   a dva jmenovci splynou. Zároveň **smaž otázku na telefon** — jinak se čísla
   dál hromadí v Sheetu, i když je aplikace neukládá.
2. Staré Sheety nech být; sync z nich čte jméno a sloupec s telefonem ignoruje.
3. Pokud jsi před migrací dělal export čísel (`export_player_numbers`), smaž ho —
   držet ho „pro jistotu" je sám o sobě problém s GDPR.

---

## 10. Zámek originu na Cloudflare 🟡

Render nemá příchozí firewall a adresa originu je veřejná, takže útočník může
Cloudflare obejít. `RequireCloudflareOriginMiddleware` proto vyžaduje sdílený
secret v hlavičce `X-Origin-Verify`, kterou přidává Cloudflare.

1. Cloudflare → Rules → **Transform Rules** → Modify Request Header → Set
   static `X-Origin-Verify: <náhodný řetězec>` pro celý hostname
2. Ověř na `/whoami/` (superuser), že hlavička opravdu přichází
3. Teprve pak nastav na Renderu `ORIGIN_SHARED_SECRET=<stejný řetězec>` —
   nastavené dřív než pravidlo běží 403ne celý web

---

## 11. Zálohy — co vlastně máme ⏱ 30 min 🔴

Tohle je jediný bod, který se **netýká útočníka**. Týká se překlepu v `DELETE`,
špatně spuštěné migrace a smazaného bucketu. Zatím není nikde napsané, co
zálohu tvoří ani jak se z ní vrací zpátky — a záloha, kterou jsi nikdy
neobnovil, není záloha, je to naděje.

### 11.1 Zjisti a zapiš, co Render drží

V dashboardu u databáze (sekce *Backups*) si ověř a doplň sem:

```
Plán:                 ...........................
Retence:              ......... dní
Frekvence:            ......... (denní / continuous PITR)
Poslední úspěšná:     ...........................
```

Na free/starter plánech je retence krátká nebo žádná. Pokud vyjde „žádná“,
je to zjištění, ne detail — buď se plán zvedne, nebo se dělá vlastní dump
(bod 11.3).

### 11.2 Zkus obnovu **do zahazovací databáze**

Nikdy ne přes produkci. Cílem je zjistit, že soubor jde načíst a data v něm
dávají smysl:

```bash
# 1. Stáhni si dump z Renderu (dashboard → Backups → Download).
# 2. Lokálně, do prázdné DB:
createdb gol_restore_test
pg_restore --no-owner --dbname=gol_restore_test dump.sql

# 3. Kontrola, že tam je to podstatné:
psql gol_restore_test -c "SELECT count(*) FROM leaderboard_user;"
psql gol_restore_test -c "SELECT count(*) FROM leaderboard_usertoevent;"
psql gol_restore_test -c "SELECT max(date) FROM leaderboard_event;"

# 4. Ukliď.
dropdb gol_restore_test
```

Zapiš si sem datum, kdy to naposled prošlo: `.......................`

### 11.3 Vlastní dump, když retence nestačí

`pg_dump` z Render shellu nebo z cronu, výstup do R2 (jiný bucket než média —
záloha vedle originálu není záloha):

```bash
pg_dump "$DATABASE_URL" --no-owner --format=custom \
  | aws s3 cp - "s3://gameofyolo-backups/db-$(date +%F).dump" \
      --endpoint-url "$AWS_S3_ENDPOINT_URL"
```

### 11.4 Média

R2 bucket s fotkami **žádnou zálohu nemá**, pokud mu nezapneš versioning.
Smazaný nebo přepsaný objekt je pryč. Zvaž zapnutí versioningu s krátkou
lifecycle policy — obrázky se nepřepisují (Django dává nové jméno při kolizi),
takže to nestojí skoro nic.

### 11.5 Co záloha *nepokrývá*

Ať to není překvapení: `MEDIA_ROOT` na disku Renderu, obsah cache (Redis) a
`credentials.json` pro Google. První dvě jsou obnovitelné, třetí se stahuje
znovu z Google Cloud Console.

---

## Shrnutí env proměnných na Renderu

```
# krok 2
ADMIN_URL=sprava-x7k2/

# krok 4 (nastavené; MEDIA_S3_ENABLED=0 jen při dalším cutoveru)
MEDIA_S3_BUCKET=gameofyolo-media
MEDIA_S3_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
MEDIA_S3_ACCESS_KEY=
MEDIA_S3_SECRET_KEY=
MEDIA_S3_REGION=auto
MEDIA_S3_CUSTOM_DOMAIN=img.gameofyolo.com

# krok 5
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# krok 6
WEB_CONCURRENCY=2
GUNICORN_THREADS=2

# krok 7 — jen dočasně na nové doméně
CSP_REPORT_ONLY=1

# krok 10 — až po ověření hlavičky na /whoami/
ORIGIN_SHARED_SECRET=

# volitelné: Sentry ingest host do CSP connect-src
CSP_EXTRA_CONNECT_SRC=https://o123456.ingest.sentry.io

# HSTS: až po ověření zvyš na rok
SECURE_HSTS_SECONDS=31536000
```

---

## Závěrečný checklist

- [ ] Cloudflare Access na admin cestě (anonymní request nedojde k Djangu)
- [ ] `ADMIN_URL` nastavená, `robots.txt` ji **neuvádí**
- [ ] `/api/v1/auth/me/` má `no-store` + `cf-cache-status: BYPASS`
- [ ] Anonymní okno nevidí data přihlášeného uživatele
- [ ] `MEDIA_ROOT` smazaný až po ověření; disk odpojený až nakonec
- [ ] Google login vytvoří účet s `is_staff=False` a GDPR souhlasem
- [ ] Heslový účet se stejným e-mailem se **nespojí** automaticky
- [ ] `WEB_CONCURRENCY × GUNICORN_THREADS` sedí s limitem spojení Postgresu
- [ ] `SECURE_HSTS_SECONDS` zvýšené na rok
- [ ] `ORIGIN_SHARED_SECRET` nastavený až po ověření hlavičky
- [ ] retence a plán záloh Renderu zapsané v bodě 11
- [ ] obnova do zahazovací DB **jednou proběhla** a je u ní datum
- [ ] versioning zapnutý na `gameofyolo-media`
