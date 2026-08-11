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

## 4. R2 pro média ⏱ 30 min 🔴

**Proč:** Média teď servíruje gunicorn z persistentního disku. Worker je
zablokovaný na celou dobu přenosu souboru — uživatel na pomalém připojení
stahující 2 MB fotku tři sekundy ti drží jeden ze čtyř workerů tři sekundy.
Přesun na R2 to z web workeru sundá úplně a obrázky jde cachovat na edgi.

Druhý důvod je provozní: disk je jedna kopie na jednom místě. R2 má vlastní
redundanci a nemusíš ho zvětšovat, až galerie poroste.

> **Pozor na pořadí — nejde to udělat jedním krokem.** V databázi je u každého
> souboru jen relativní klíč (`event_images/party.jpg`); URL se skládá až za
> běhu podle aktivního storage backendu. Jakmile přepneš na S3, **všechny**
> existující URL okamžitě míří do bucketu — i ty soubory, které tam ještě
> nejsou. Kdyby ses přepnul a teprve pak kopíroval, celá galerie je po dobu
> nahrávání rozbitá.
>
> Proto jsou dvě proměnné: `MEDIA_S3_*` (přístupové údaje) a `MEDIA_S3_ENABLED`
> (jestli se z něj opravdu servíruje). Nejdřív zkopíruj s vypnutým přepínačem,
> ověř, a teprve pak přepni.

### 4.1 Vytvoř bucket

1. Cloudflare → **R2** → Create bucket → `gameofyolo-media`
2. Settings → **Public access** → Connect a domain → `img.gameofyolo.com`
3. R2 → **Manage API tokens** → Create token (Object Read & Write pro ten bucket)

> Servíruj z `img.gameofyolo.com`, ne z hlavní domény. Kdyby někdo nahrál SVG
> s embedded skriptem a ty ho servíruješ ze stejného originu jako appku, ten
> skript běží v tvém originu a má přístup k cookies. Z jiné domény je neškodný.

### 4.2 Fáze 1 — údaje ano, přepínač ne

Render → Environment. Všimni si `MEDIA_S3_ENABLED=0`:

```
MEDIA_S3_BUCKET=gameofyolo-media
MEDIA_S3_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
MEDIA_S3_ACCESS_KEY=...
MEDIA_S3_SECRET_KEY=...
MEDIA_S3_REGION=auto
MEDIA_S3_CUSTOM_DOMAIN=img.gameofyolo.com
MEDIA_S3_ENABLED=0
```

Po deployi se navenek **nic nezmění** — appka pořád servíruje z disku. Jen má
teď přístup do bucketu.

### 4.3 Fáze 2 — zkopíruj a ověř

V Render shellu (Shell tab), v tomhle pořadí:

```bash
python3 manage.py migrate_media_to_s3 --dry-run   # co by se nahrálo
python3 manage.py migrate_media_to_s3             # nahraj
python3 manage.py migrate_media_to_s3 --verify    # ověř, že tam všechno je
```

Příkaz vypíše zdroj i cíl, nikdy nic lokálně nemaže a jde bezpečně opakovat —
už nahrané klíče přeskočí. Když spadne spojení, prostě ho pusť znovu.

`--verify` skončí nenulovým kódem, pokud v bucketu něco chybí. Dokud neprojde,
**nepokračuj**.

Ověř si i to, že soubor v bucketu je vidět z CDN:

```bash
curl -I https://img.gameofyolo.com/event_images/<nejaky-soubor>.jpg
# 200, a při druhém volání cf-cache-status: HIT
```

### 4.4 Fáze 3 — přepni

```
MEDIA_S3_ENABLED=1
```

Deploy. Teď se obrázky servírují z R2 a všechny bajty tam už jsou.

**Ověření:** otevři galerii a detail akce, v DevTools → Network zkontroluj, že
obrázky chodí z `img.gameofyolo.com` a vrací 200. Pak pošli odkaz na akci do
WhatsAppu — musí se ukázat náhledový obrázek (link preview čte obrázek přes
storage API, takže tohle je zároveň test, že cutover nerozbil OG tagy).

### 4.5 Úklid disku

Teprve teď smaž obsah `MEDIA_ROOT` na disku. Chvíli ho tam ale nech — je to
tvoje jediná záloha, dokud si nejsi jistý, že je v R2 všechno v pořádku.
Persistentní disk na Renderu můžeš odpojit (a přestat za něj platit) až potom.

Zapni ještě Cloudflare → Speed → Optimization → **Polish** (WebP/AVIF podle
`Accept` hlavičky klienta, bez práce navíc).

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

Render → Settings → Start command:

```bash
gunicorn mysite.wsgi --worker-class gthread --workers 4 --threads 8 --timeout 30 --bind 0.0.0.0:$PORT
```

4 procesy × 8 vláken = 32 souběžných requestů. GIL se při čekání na DB uvolňuje,
takže u I/O-bound zátěže to funguje.

⚠ **Zkontroluj limit spojení do Postgresu.** 32 vláken = až 32 spojení.
`CONN_MAX_AGE` je v settings 600 s. Pokud má tvoje instance limit 20, sniž
`--threads` nebo přidej PgBouncer.

---

## 7. CSP — zapnutí naostro ⚪ (za týden)

CSP teď běží v **report-only** režimu: hlásí porušení, ale nic neblokuje.

Nech to tak alespoň týden, projdi reporty v konzoli prohlížeče, a teprve pak:

```
CSP_ENFORCE=1
```

⚠ **Před zapnutím otevři Django admin a koukni do konzole.** Admin používá
inline `<script>` bloky, takže striktní `script-src` může rozbít jeho widgety
(date picker, inline formsety) — a na rozdíl od SPA se to nikde na serveru
neprojeví. Řešení je vyjmout admin cestu, ne oslabit `script-src` pro celý web.

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

## 9. Odstranění telefonních čísel ⏱ 15 min 🔴

Migrace `leaderboard/0026_drop_user_phone_number` **maže sloupec s telefonními
čísly a nejde vrátit zpět**. Identitou hráče v syncu je nově e-mail z formuláře,
u starších listů jméno (`tasks.resolve_player`).

Pořadí kroků je závazné:

1. **Zálohu čísel udělej dřív, než migrace poběží.** Na Renderu ve web shellu:

   ```
   cd djangotutorial && /usr/bin/python3 manage.py export_player_numbers -o /tmp/cisla.csv
   ```

   Soubor si stáhni k sobě, ne do repa (`player_numbers_*.csv` je sice
   gitignorovaný, ale `/tmp` na Renderu deploy nepřežije). Po migraci už čísla
   nikde nejsou — kromě databázové zálohy Renderu.

   ⚠ Ten export je seznam jmen a telefonních čísel. Nedávej ho na Disk ani do
   mailu a smaž ho, jakmile bude jasné, že ho nikdo nepotřeboval. Držet ho
   „pro jistotu" navždy je samo o sobě problém s GDPR.

2. **Deploy** — `build.sh` migraci spustí sám.

3. **V Google Forms u každého nového formuláře zapni „Shromažďovat e-mailové
   adresy" (Nastavení → Odpovědi).** Bez toho se hráči párují jen podle jména a
   dva jmenovci splynou v jednoho. Zároveň **smaž otázku na telefon** — jinak ji
   lidi pořád vyplňují a čísla se hromadí v Sheetu, i když je aplikace neukládá.

4. **Staré Sheety** nech být. Sync z nich čte jméno; sloupec s telefonem ignoruje.
   Pokud chceš čísla vyčistit i tam, musíš to udělat ručně v Google Sheets —
   aplikace do nich nikdy nezapisuje.

5. Zkontroluj, že zásady ochrany osobních údajů (`/ochrana-osobnich-udaju`) už
   telefon neuvádí. Text je upravený, `PRIVACY_POLICY_VERSION` **zůstala
   nezměněná** — je to změna ve prospěch uživatelů, nová vlna souhlasů se kvůli
   ní vyžadovat nemusí. Bump zvaž, pokud text budeš upravovat i jinde.

---

## Shrnutí env proměnných na Renderu

```
# krok 2
ADMIN_URL=sprava-x7k2/

# krok 4
MEDIA_S3_BUCKET=gameofyolo-media
MEDIA_S3_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
MEDIA_S3_ACCESS_KEY=
MEDIA_S3_SECRET_KEY=
MEDIA_S3_REGION=auto
MEDIA_S3_CUSTOM_DOMAIN=img.gameofyolo.com
MEDIA_S3_ENABLED=0   # → 1 teprve až --verify projde

# krok 5
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# krok 7 (až za týden)
CSP_ENFORCE=1

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
- [ ] `--verify` prošlo, teprve pak `MEDIA_S3_ENABLED=1`
- [ ] Fotky se načítají z `img.gameofyolo.com`
- [ ] Link preview (WhatsApp) po přepnutí pořád ukazuje obrázek
- [ ] `MEDIA_ROOT` smazaný až po ověření; disk odpojený až nakonec
- [ ] Google login vytvoří účet s `is_staff=False` a GDPR souhlasem
- [ ] Heslový účet se stejným e-mailem se **nespojí** automaticky
- [ ] `gthread` worker, počet vláken sedí s limitem Postgresu
- [ ] CSP reporty čisté → `CSP_ENFORCE=1`
- [ ] `SECURE_HSTS_SECONDS` zvýšené na rok

---

## 10. Zálohy — co vlastně máme ⏱ 30 min 🔴

Tohle je jediný bod, který se **netýká útočníka**. Týká se překlepu v `DELETE`,
špatně spuštěné migrace a smazaného bucketu. Zatím není nikde napsané, co
zálohu tvoří ani jak se z ní vrací zpátky — a záloha, kterou jsi nikdy
neobnovil, není záloha, je to naděje.

### 10.1 Zjisti a zapiš, co Render drží

V dashboardu u databáze (sekce *Backups*) si ověř a doplň sem:

```
Plán:                 ...........................
Retence:              ......... dní
Frekvence:            ......... (denní / continuous PITR)
Poslední úspěšná:     ...........................
```

Na free/starter plánech je retence krátká nebo žádná. Pokud vyjde „žádná“,
je to zjištění, ne detail — buď se plán zvedne, nebo se dělá vlastní dump
(bod 10.3).

### 10.2 Zkus obnovu **do zahazovací databáze**

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

### 10.3 Vlastní dump, když retence nestačí

`pg_dump` z Render shellu nebo z cronu, výstup do R2 (jiný bucket než média —
záloha vedle originálu není záloha):

```bash
pg_dump "$DATABASE_URL" --no-owner --format=custom \
  | aws s3 cp - "s3://gameofyolo-backups/db-$(date +%F).dump" \
      --endpoint-url "$AWS_S3_ENDPOINT_URL"
```

### 10.4 Média

R2 bucket s fotkami **žádnou zálohu nemá**, pokud mu nezapneš versioning.
Smazaný nebo přepsaný objekt je pryč. Zvaž zapnutí versioningu s krátkou
lifecycle policy — obrázky se nepřepisují (Django dává nové jméno při kolizi),
takže to nestojí skoro nic.

- [ ] versioning zapnutý na `gameofyolo-media`

### 10.5 Co záloha *nepokrývá*

Ať to není překvapení: `MEDIA_ROOT` na disku Renderu, obsah cache (Redis) a
`credentials.json` pro Google. První dvě jsou obnovitelné, třetí se stahuje
znovu z Google Cloud Console.

### Do závěrečného checklistu

- [ ] retence a plán Renderu zapsané výš
- [ ] obnova do zahazovací DB **jednou proběhla** a je u ní datum
- [ ] R2 versioning na médiích
