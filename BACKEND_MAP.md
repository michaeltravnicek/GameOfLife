# Backend Map — orientace ve vlastním backendu

> Cíl tohohle dokumentu: **abys tenhle backend uměl sám udržovat, rozšiřovat a posoudit** —
> bez toho, aby ti někdo musel vysvětlovat, co která vrstva dělá.
> Není to tutoriál Djanga (to umíš). Je to mapa TVOJÍ codebase + upřímné hodnocení, čemu věřit.
> Verze: 2026-08-12. Stav: 16 700 řádků Pythonu (bez migrací), 607 testů, všechny procházejí.

---

## 0. Hlavní zpráva na úvod

Prošel jsem backend celý. **Není to guláš.** Má jasnou vrstevnatou architekturu, konzistentní
konvence a nadprůměrné komentáře — na hodně místech je u rozhodnutí napsané *proč*, ne jen *co*
(např. proč `grant_django_admin_access` není v `save()`, proč `CompressedStaticFilesStorage`
a ne manifest varianta, proč `/media/` neservíruje WhiteNoise). To je přesně ta věc, která
codebase drží pochopitelnou, když se k ní vrátíš za rok.

Kde ti to připadá jako guláš, není to kvalitou kódu — je to **množstvím konceptů**. Backend má
16 modelů, 4 role, 3 druhy cache, dvě různé „identity uživatele" a integraci na Google.
To je hodně věcí, ale každá z nich má jedno místo, kde žije. Tenhle dokument je seznam těch míst.

**Kdyby to měl někdo přepisovat, není proč.** Věci, které bych označil za dluh, jsou na konci
(kapitola 7) a jsou to drobnosti, ne strukturální problémy.

---

## 1. Architektura ve vrstvách

Django projekt má tři aplikace a jasné dělení odpovědnosti. Tohle je ta nejdůležitější tabulka
v dokumentu:

| Vrstva | Kde | Odpovědnost | Co tam NEPATŘÍ |
|---|---|---|---|
| **URL routing** | [urls.py](djangotutorial/mysite/urls.py), [api/urls.py](djangotutorial/leaderboard/api/urls.py) | cesta → funkce | logika |
| **View** | [api/views.py](djangotutorial/leaderboard/api/views.py) | oprávnění, parsování parametrů, HTTP status, transakce | dotazy do DB, výpočty |
| **Serializer** | [api/serializers.py](djangotutorial/leaderboard/api/serializers.py) | validace vstupu, tvar výstupního JSONu | business pravidla |
| **Service** | [services/](djangotutorial/leaderboard/services/) | business logika, dotazy, cache | HTTP věci (`request`, `Response`) |
| **Model** | [models.py](djangotutorial/leaderboard/models.py) | data, DB constraints, invalidace cache | prezentace |

Pravidlo, které kód dodržuje a **ty ho dodržuj taky**:
**view je tenký.** Podívej se na `event_create` ([views.py:646](djangotutorial/leaderboard/api/views.py#L646)) —
9 řádků: zvaliduj, atomicky ulož, vrať. Veškerá práce je v serializeru a service.

Když budeš přidávat endpoint a začne ti view růst přes ~25 řádků, logika patří do `services/`.

---

## 2. Životní cyklus requestu (dvě konkrétní cesty)

### A) Čtení: `GET /api/v1/events/?city=Brno`

```
1. gunicorn                      → WSGI, předá Djangu
2. MIDDLEWARE (settings.py:317)  → Security → WhiteNoise (netrefa, jde dál)
                                   → CSP → CORS → Session → CSRF → Auth → Axes
3. mysite/urls.py                → prefix "api/v1/" → leaderboard.api.urls
4. leaderboard/api/urls.py       → "events/" → views.events_list
5. @permission_classes([AllowAny]) → projde i nepřihlášený
6. views.events_list             → přečte GET parametry, zavolá službu
7. services/events.list_events   → ORM dotaz (+ cache), vrátí queryset
8. EventListSerializer           → modely → dicty
9. Response(...)                 → DRF vyrenderuje JSON
10. middleware zpátky nahoru     → přidá hlavičky (CSP, CORS, Vary…)
```

### B) Zápis: `POST /api/v1/events/create/`

Stejné do kroku 4, pak:
```
5. @permission_classes([IsAdmin]) → accounts/permissions.py přečte Profile.role
                                    → není-li "admin", 403 a konec
6. CSRF middleware si už dřív ověřil X-CSRFToken proti cookie
7. EventWriteSerializer.is_valid(raise_exception=True) → 400 s chybami polí
8. with transaction.atomic():     → serializer.save() → Event.save()
                                       ├─ vygeneruje slug (unikátní)
                                       ├─ resize_image + make_webp_variant
                                       └─ invalidate_event_caches()
9. EventDetailSerializer → 201 Created
```

**Tohle si zapamatuj:** `transaction.atomic()` obaluje i sestavení odpovědi. Kdyby serializace
odpovědi spadla, řádek se odroluje — nezůstane půlka akce v DB. Je to konvence celého projektu
(viz [CLAUDE.md](CLAUDE.md), „Write endpoints must be transactional").

---

## 3. Datový model — a jeden koncept, který musíš mít v hlavě

### ⭐ Dvě různé „identity uživatele"

Tohle je **jediný netriviální koncept celého backendu.** Když ho pochopíš, model přestane být
matoucí.

```
auth.User                 accounts.Profile              leaderboard.User
(Django, login)  ──1:1──► (role, bio, foto,   ──1:1──►  (jméno + e-mail,
 username, heslo           privacy flagy)       (může      hráč z Google Sheets)
 e-mail                                          být            │
                                                 NULL)          ├─ UserToEvent (body)
     │                                                          ├─ UserBadge (odznaky)
     ├─ EventRSVP (přihlášení na akci)                          └─ EventFeedback
     ├─ UserPhoto / PhotoLike (galerie)
     └─ ProfileAnswer
```

**Proč to tak je:** body a účast vznikaly v Google Sheets dávno předtím, než někdo měl účet.
Hráč byl identifikovaný údajem z formuláře k akci, ne loginem — dřív telefonním číslem, pak
e-mailem (`leaderboard.User.email`), u starších listů jménem; viz `tasks.resolve_player`.

**Dnes je to obráceně:** registrace zakládá hráče rovnou
([accounts.services.ensure_leaderboard_user](djangotutorial/accounts/services.py)), takže účet
*je* hráč a bez toho by se ani nemohl checkinovat. Co zbývá, je archiv z formulářů —
řádky, které patří někomu, kdo se zaregistroval až potom. Ty se **slučují**
([leaderboard/merging.py](djangotutorial/leaderboard/merging.py)), návrhy dává
[accounts/matching.py](djangotutorial/accounts/matching.py) a **potvrzuje je admin**.
Automaticky se spojí jen přesná shoda e-mailu.

Sloučení je měkké: `User.merged_into` řádek nechá v DB a jen ho vyřadí ze žebříčku, takže
omyl jde vrátit. Proto `User.objects` **vidí jen aktivní hráče** — na sloučené se dostaneš
přes `User.all_objects`.

**Praktický důsledek, na který narazíš:**
- Vše, co souvisí s **body, účastí, odznaky a hodnocením** → visí na `leaderboard.User`.
- Vše, co souvisí s **webovým účtem** (RSVP, fotky, lajky) → visí na `auth.User`.
- `Profile.leaderboard_user` **může být `None`** u účtů starších než `ensure_leaderboard_user`
  (dorovná je `manage.py backfill_player_accounts`). Pořád s tím počítej — je to nejčastější
  zdroj `AttributeError` v novém kódu.
- Hráč připojený k účtu se nikdy nesmí stát *zdrojem* sloučení; `merge_players` to odmítne.

### Zbytek modelů (16 celkem)

| Model | K čemu | Zvláštnost |
|---|---|---|
| `Season` | sezóny žebříčku | partial unique index: **max jedna aktivní** |
| `Event` | akce | `slug` se generuje v `save()`; geo pole musí být pár (DB constraint) |
| `Category` | kategorie akcí | `save()`+`delete()` invalidují cache |
| `Badge` | odznak **A ZÁROVEŇ logo akce** | jedna artwork sdílená mnoha akcemi (dřív 135 souborů = 7 obrázků) |
| `UserToEvent` | účast + body | `unique_together` |
| `UserBadge` | sbírka odznaků | odznak zůstane, i když se smaže účast |
| `EventRSVP` | přihlášení na akci | ≠ účast! |
| `EventFeedback` | hodnocení 1–10 | zdroj `web` nebo `form` (Google Form sync) |
| `UserPhoto`, `PhotoLike` | galerie | |
| `ImageToEvent` | oficiální fotky akce | |
| `ProfileQuestion`, `ProfileAnswer` | otázky na profilu | |
| `LastUpdate` | kdy naposled běžel sync | |

**Pozor na `EventRSVP` vs `UserToEvent`** — přihlášený ≠ dorazil. Žebříček počítá jen `UserToEvent`.

---

## 4. Mapa souborů: co je co a kdy na to sáhneš

### `leaderboard/` — jádro

| Soubor | Co dělá | Kdy to otevřeš | Priorita |
|---|---|---|---|
| [models.py](djangotutorial/leaderboard/models.py) (456ř) | 15 modelů | při každé změně dat | 🔴 čti první |
| [api/views.py](djangotutorial/leaderboard/api/views.py) (827ř) | 30 endpointů | při každé změně API | 🔴 |
| [api/serializers.py](djangotutorial/leaderboard/api/serializers.py) (593ř) | tvar JSONu dovnitř i ven | s views | 🔴 |
| [api/urls.py](djangotutorial/leaderboard/api/urls.py) | mapa endpointů | **nejlepší rozcestník** | 🔴 |
| [services/leaderboard.py](djangotutorial/leaderboard/services/leaderboard.py) | výpočet žebříčku, pořadí, sezóny | logika bodů | 🟠 |
| [services/events.py](djangotutorial/leaderboard/services/events.py) | filtrování a výpis akcí | filtry | 🟠 |
| [services/home.py](djangotutorial/leaderboard/services/home.py) | hero, statistiky, aktivní check-in | homepage | 🟠 |
| [services/attendance.py](djangotutorial/leaderboard/services/attendance.py) | účast a body u akce | admin správa účasti | 🟠 |
| [services/gallery.py](djangotutorial/leaderboard/services/gallery.py), [badges.py](djangotutorial/leaderboard/services/badges.py), [catalog.py](djangotutorial/leaderboard/services/catalog.py), [feedback.py](djangotutorial/leaderboard/services/feedback.py) | dle názvu | | 🟡 |
| [cache_config.py](djangotutorial/leaderboard/cache_config.py) | **všechny cache klíče + TTL na jednom místě** | přidáváš cache | 🟠 |
| [privacy.py](djangotutorial/leaderboard/privacy.py) | vynucení privacy flagů | ❗ každý nový endpoint s profilem | 🔴 |
| [checkin.py](djangotutorial/leaderboard/checkin.py) | geo check-in (vzdálenost, časové okno) | | 🟡 |
| [image_utils.py](djangotutorial/leaderboard/image_utils.py) | resize, validace uploadu, WebP | ❗ každý upload | 🟠 |
| [tasks.py](djangotutorial/leaderboard/tasks.py) + [sheet_columns.py](djangotutorial/leaderboard/sheet_columns.py) | Google Sheets sync | | 🟡 |
| [google_form.py](djangotutorial/leaderboard/google_form.py) | načtení a odeslání Google Formu | | 🟡 |
| [signals.py](djangotutorial/leaderboard/signals.py) | udělení odznaku při účasti | | 🟡 |
| [merging.py](djangotutorial/leaderboard/merging.py) | ⭐ sloučení dvou hráčů (měkké, vratné) | ❗ hýbe cizími body | 🔴 |
| [admin.py](djangotutorial/leaderboard/admin.py) | Django admin | jen ruční opravy | 🟡 |

### `accounts/` — účty, role, profily

| Soubor | Co dělá | Priorita |
|---|---|---|
| [models.py](djangotutorial/accounts/models.py) | `Profile`: role, privacy flagy, GDPR souhlas | 🔴 |
| [permissions.py](djangotutorial/accounts/permissions.py) | `IsAdmin`, `IsAdminOrPhotographer` + helpery | 🔴 |
| [matching.py](djangotutorial/accounts/matching.py) | ⭐ návrh, kterému účtu archivní hráč patří (potvrzuje admin) | 🟠 |
| [services.py](djangotutorial/accounts/services.py) (411ř) | logika profilů a sestavení payloadu | 🟠 |
| [api/views.py](djangotutorial/accounts/api/views.py) | login, registrace, reset hesla, profil | 🟠 |
| [adapters.py](djangotutorial/accounts/adapters.py) | Google login (allauth) | 🟡 |
| [api/throttles.py](djangotutorial/accounts/api/throttles.py) | rate limity na auth endpointy | 🟡 |

**Role systém** je jednoduchý a celý v [permissions.py](djangotutorial/accounts/permissions.py):
`admin` > `photographer` > `close` > `""`. Není hierarchický obecně — každý helper si vyjmenuje,
koho pouští (`_STAFF_ROLES`, `_CLOSE_OR_ABOVE_ROLES`). To je **záměrně explicitní**, nedělej z toho
chytré dědění.

### `mysite/` — projekt

| Soubor | Co dělá |
|---|---|
| [settings.py](djangotutorial/mysite/settings.py) (836ř) | konfigurace — **hodně komentářů, dá se číst jako dokumentace** |
| [urls.py](djangotutorial/mysite/urls.py) | rezervované prefixy + catch-all na React |
| [views.py](djangotutorial/mysite/views.py) | `react_index` (servíruje SPA), `robots.txt`, `whoami` |
| [og.py](djangotutorial/mysite/og.py) (423ř) | Open Graph tagy pro crawlery (respektuje privacy!) |
| [middleware.py](djangotutorial/mysite/middleware.py) | `AdminCSPExemptMiddleware`, `Debug500Middleware` |
| [drf.py](djangotutorial/mysite/drf.py) | DRF nastavení / exception handling |
| [test_settings.py](djangotutorial/mysite/test_settings.py) | in-memory SQLite → testy bez Postgresu |

---

## 5. Průřezové mechanismy (pět věcí, které prostupují vším)

### 5.1 Cache
Všechny klíče a TTL jsou na jednom místě: [cache_config.py](djangotutorial/leaderboard/cache_config.py).
Invalidace se volá z `save()` modelů. TTL je odstupňované podle toho, jak rychle se data mění
(žebříček 5 min, kategorie 1 h).

**Pravidlo:** nová cache = nový klíč + TTL **do `cache_config.py`**, nikdy inline v service.

### 5.2 Privacy flagy
`hide_pts`, `hide_events`, `members_only` na `Profile`. Vynucuje je
`privacy.visibility_for(profile, viewer)` — a **každý** endpoint, který vrací cizí profil,
tím musí projít. Vlastník a admin nejsou nikdy omezeni. Platí to i pro
[og.py](djangotutorial/mysite/og.py) (crawler nesmí vidět víc než člověk).

### 5.3 Oprávnění
Vždy deklarativně přes `@permission_classes([...])` u view. Žádné `if request.user...` uvnitř.
Když čteš neznámý endpoint, **první řádek, na který se koukni, je permission_classes.**

### 5.4 Transakce
Každý zápis v `transaction.atomic()`, včetně sestavení odpovědi.

### 5.5 Obrázky
`resize_image()` + `make_webp_variant()` volané ze `save()` modelu; `validate_upload()`
na cokoli od uživatele. Rozměry se liší podle účelu (badge 512, profil 400, event 1200, galerie 1600).

---

## 6. Doporučené pořadí čtení (a cvičení)

**Den 1 — kostra (2 h):**
1. [api/urls.py](djangotutorial/leaderboard/api/urls.py) — přečti celý, je to obsah knihy.
2. [models.py](djangotutorial/leaderboard/models.py) — celý, včetně komentářů.
3. Nakresli si na papír diagram dvou identit uživatele z kapitoly 3. **Bez koukání.**

**Den 2 — jedna cesta skrz (2 h):**
Vyber si `GET /api/v1/events/` a projdi ji od `urls.py` po JSON. U každé vrstvy si řekni,
co by se stalo, kdyby tam nebyla.

**Den 3 — jeden zápis (2 h):**
To samé pro `POST /api/v1/events/create/`. Sleduj: permission → serializer → atomic → save() →
invalidace cache.

**Den 4 — cvičení, které to potvrdí:**
Přidej triviální endpoint, třeba `GET /api/v1/events/<slug>/feedback-summary/`
(průměr hodnocení + počet). Dotkne se všech vrstev: urls → view → service → serializer → test.
Když to zvládneš sám, backend umíš.

---

## 7. Upřímné hodnocení kvality

### Co je opravdu dobře
- **Vrstvení je konzistentní.** Views tenké, logika v services. Držené napříč všemi 30 endpointy.
- **Komentáře vysvětlují *proč*.** Tohle je vzácné a je to hlavní důvod, proč se v tom dá
  zorientovat bez autora.
- **DB constraints, ne jen Python validace.** `CheckConstraint` a partial unique indexy hlídají
  invarianty i pro bulk cesty (sheets sync), které obcházejí `clean()`.
- **607 testů, všechny procházejí**, a pokrývají to podstatné: privacy flagy, bezpečnost,
  oprávnění, check-in, párování účtů, sync, mazání účtu, health check.
- **Bezpečnost je promyšlená** — role deklarativně, CSRF, axes, CSP, obskurní admin URL,
  throttling na auth.
- **Cache má jedno místo.**

### Dluh (drobnosti, nic strukturálního)
1. **[api/views.py](djangotutorial/leaderboard/api/views.py) má 874 řádků.** Pořád čitelné, ale
   blíží se hranici. Přirozený řez je `views/events.py`, `views/admin.py`, `views/gallery.py`.
   Zatím bych nechal — dělej to, až přeteče přes ~1000.
2. **`WHITENOISE_AUTOREFRESH = True` bez ohledu na `DEBUG`**
   ([settings.py:728](djangotutorial/mysite/settings.py#L728)) — v produkci `os.stat()` navíc
   u každého statického requestu. Patří do `if DEBUG:`.
3. ~~**[CLAUDE.md](CLAUDE.md) tvrdí 377 testů**, reálně je jich 454.~~ Opraveno — teď 607,
   a tenhle dokument sám uváděl na třech místech tři různá čísla (465 / 454 / 459).
   Zůstává poučení: dokumentaci, které se nedá věřit v číslech, se hůř věří i jinde.
4. **[settings.py](djangotutorial/mysite/settings.py) má 895 řádků.** Pro jednu appku je to hodně,
   ale komentáře jsou tam právem — nedělil bych.
5. **`Profile.leaderboard_user` může být `None`** a není to typově vynucené. Kód s tím počítá,
   ale je to trvalý zdroj pozornosti u nového kódu.

**Verdikt: tohle je nadprůměrně napsaný Django projekt.** Kdyby na něm zítra musel pracovat cizí
senior, zorientuje se za den. To je ta správná metrika, a splňuje ji.

---

## 8. Jak si cokoliv ověříš sám (bez cizí pomoci)

Tohle je nejdůležitější kapitola pro tvůj cíl. Nástroje, kterými si **ověříš tvrzení o vlastním kódu**:

```bash
cd djangotutorial

# 1. Testy — jediná objektivní pravda o tom, jestli něco funguje.
DJANGO_SETTINGS_MODULE=mysite.test_settings DJANGO_SECRET_KEY=x \
  /usr/bin/python3 manage.py test leaderboard accounts

# Jen jeden modul, když ladíš:
DJANGO_SETTINGS_MODULE=mysite.test_settings DJANGO_SECRET_KEY=x \
  /usr/bin/python3 manage.py test leaderboard.tests.test_privacy_flags -v 2

# 2. Interaktivní shell nad reálnými daty — nejrychlejší způsob, jak něco ověřit.
/usr/bin/python3 manage.py shell
>>> from leaderboard.models import Event
>>> Event.objects.filter(visible_to_users=True).count()

# 3. Uvidíš skutečné SQL, které ORM generuje:
>>> print(Event.objects.filter(place="Brno").query)

# 4. Nezapomenutá migrace?
/usr/bin/python3 manage.py makemigrations --check --dry-run

# 5. Kontrola konfigurace pro produkci:
/usr/bin/python3 manage.py check --deploy

# 6. Swagger — klikací dokumentace VŠECH endpointů, generovaná z kódu.
#    Běží jen v DEBUG: spusť runserver a otevři http://localhost:8000/api/schema/swagger/
```

**Zlaté pravidlo nezávislosti:** když ti kdokoliv (včetně AI) řekne, jak se tenhle kód chová,
ověř to testem nebo shellem. Trvá to dvě minuty a je to jediný způsob, jak si udržet jistotu.

---

### TL;DR
Backend je zdravý, vrstvený a otestovaný — přepisovat není co. Jediný koncept, který si musíš
pořádně usadit, jsou **dvě identity uživatele** (`auth.User` vs `leaderboard.User`, spojené přes
`Profile`, dnes ručně přes admin). Rozcestník při jakékoli změně je
[api/urls.py](djangotutorial/leaderboard/api/urls.py). Logika patří do `services/`, ne do views.
A všechno, co ti kdo o tomhle kódu řekne, si umíš ověřit sám podle kapitoly 8.
