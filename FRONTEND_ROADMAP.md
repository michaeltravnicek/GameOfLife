# Frontend Roadmap — co se naučit, abys plynně upravoval GameOfLive

> Osobní studijní plán pro **tebe** (Django solidní, CSS ~5/10, React: komponenty chápeš, hooky slabší).
> Napsáno podle skutečného kódu v `frontend/`, ne podle obecných tutoriálů.
> Verze: 2026-06-20.

---

## 0. Čti nejdřív tohle (upřímné zhodnocení)

Tvůj frontend **není** začátečnický React. Je to produkční **React 19 SPA** s věcmi, které píšou senioři:

- vlastní **stale-while-revalidate cache** s deduplikací a retry ([queryCache.js](frontend/src/services/queryCache.js)) — ručně napsaná zmenšenina knihovny TanStack Query,
- **code splitting** přes `lazy()` + `Suspense` ([App.jsx](frontend/src/App.jsx)),
- **callback refs** a `IntersectionObserver` ([useReveal.js](frontend/src/hooks/useReveal.js)),
- **Axios interceptory** pro CSRF i token auth ([api.js](frontend/src/services/api.js)),
- **Capacitor** wrapper pro iOS/Android.

Dobrá zpráva: **abys mohl bezpečně upravovat 80 % kódu, nepotřebuješ rozumět všemu.** Potřebuješ pevně jeden blok — **hooky a render model Reactu** — a zbytek se dá číst „od povrchu dovnitř".

### Klíčový insight o tvojí mezeře

> **„Hooky mi nejdou" skoro vždy znamená „nejsou mi vlastní JS closures, asynchronní kód a referenční identita objektů."**

Hooky samy o sobě jsou triviální API (`const [x, setX] = useState(0)`). Těžké je to *kolem*: proč se efekt spustí dvakrát, proč funkce v dependency array způsobí smyčku, proč `useRef` přežije render a `useState` taky, ale jinak. To je JavaScript, ne React. Proto **Fáze 1 (JS základy) není volitelná** — je to skrytý prerekvizit, který odemkne všechno ostatní.

### Jak číst tuhle roadmapu

Každá fáze má: **proč to v TVÉM kódu potřebuješ** → **co pochopit** → **kde se to děje (soubor)** → **zdroj**. Fáze jsou seřazené podle závislostí — neskákej dopředu, dokud nemáš předchozí.

Priorita: 🔴 nezbytné pro jakoukoliv úpravu · 🟠 potřeba při běžné práci · 🟡 až když na to narazíš.

---

## 1. Mapa technologií v projektu

| Technologie | K čemu v projektu slouží | Kde to žije | Tvoje priorita |
|---|---|---|---|
| **JavaScript (ES2020+)** | jazyk všeho ve `frontend/` | celý `src/` | 🔴 |
| **React 19** | celé UI, komponenty, stav | `src/components`, `src/pages` | 🔴 |
| **React Hooks** | stav, efekty, sdílení logiky | všude | 🔴 |
| **JSX** | šablonovací syntaxe v JS | každý `.jsx` | 🔴 |
| **React Router 7** | routing SPA, URL → stránka | [App.jsx](frontend/src/App.jsx) | 🟠 |
| **Context API** | globální stav (přihlášený uživatel) | [AuthContext.jsx](frontend/src/context/AuthContext.jsx) | 🟠 |
| **Axios** | HTTP volání na Django API | [api.js](frontend/src/services/api.js) | 🟠 |
| **Vlastní query cache** | cache + dedup + retry odpovědí | [queryCache.js](frontend/src/services/queryCache.js) | 🟠 |
| **CSS (moderní, bez frameworku)** | vzhled, layout, design tokeny | `src/styles`, `*.css` u komponent | 🔴 (tvoje slabina) |
| **Vite 8** | dev server, build, proxy na Django | [vite.config.js](frontend/vite.config.js) | 🟡 |
| **Capacitor 8** | obal SPA do iOS/Android appky | `frontend/ios`, `frontend/android` | 🟡 |
| **Leaflet / react-leaflet** | mapa u detailu eventu | [EventLocationMap](frontend/src/components/EventLocationMap) | 🟡 |
| **Vitest + Testing Library** | testy | `*.test.jsx` | 🟡 |

Co **nemusíš** řešit: TypeScript (projekt je čistý JS + JSX; `@types/react` je jen pro našeptávač), Redux/Zustand (nepoužívá se — stav je Context + lokální `useState`), žádný CSS framework (Tailwind/Bootstrap tu nejsou).

---

## 2. Fáze 1 — JavaScript, který drží React (🔴 skrytý prerekvizit)

**Proč:** každý řádek hooků stojí na těchhle věcech. Když ti nejsou vlastní, hooky budou navždy „magie".

| Co pochopit | Proč to v kódu potřebuješ | Reálný příklad |
|---|---|---|
| **ES moduly** `import`/`export` | každý soubor importuje | [api.js](frontend/src/services/api.js) řádky 1–6 |
| **Arrow funkce** `() => {}` | handlery, callbacky, fetchery | `onClick={() => setMenuOpen((o) => !o)}` v [Nav.jsx:138](frontend/src/components/Nav/Nav.jsx#L138) |
| **Destructuring** `const { user } = ...` | props, návratové hodnoty hooků | `const { user, logout } = useAuth()` [Nav.jsx:22](frontend/src/components/Nav/Nav.jsx#L22) |
| **Spread/rest** `...` | merge objektů, kopie polí | `[...firstItems, ...extraItems]` [usePaginatedQuery.js:65](frontend/src/services/usePaginatedQuery.js#L65) |
| **Optional chaining** `?.` | bezpečný přístup k API datům | `error?.response?.status` [api.js:46](frontend/src/services/api.js#L46) |
| **Nullish coalescing** `??` | výchozí hodnoty | `r.count ?? 0` [EventsPage.jsx:18](frontend/src/pages/Events/EventsPage.jsx#L18) |
| **Array metody** `map/filter/sort/some/find` | renderování seznamů, filtry | `upcoming.map((ev) => ...)` [EventsPage.jsx:238](frontend/src/pages/Events/EventsPage.jsx#L238) |
| **Closures** ⭐ | **PROČ hooky fungují** | scroll handler „si pamatuje" `lastY` v [Nav.jsx:36](frontend/src/components/Nav/Nav.jsx#L36) |
| **Promises + async/await** | každé API volání | `const data = await apiLogin(...)` [AuthContext.jsx:30](frontend/src/context/AuthContext.jsx#L30) |
| **Ternární operátor v JSX** | podmíněné renderování | `{user ? (...) : (...)}` [Nav.jsx:153](frontend/src/components/Nav/Nav.jsx#L153) |

⭐ **Closures jsou ta nejdůležitější věc celé Fáze 1.** Funkce v JS „uzavře" proměnné z místa, kde vznikla, a nese si je s sebou. Přesně proto si `useState` pamatuje hodnotu mezi rendery a proč „stale closure" (zastaralá hodnota v efektu) je nejčastější React bug. Než půjdeš dál, musíš umět vysvětlit, proč tohle vytiskne `0`, ne `1`:
```js
let count = 0;
const read = () => count;   // closure nad `count`
count = 1;
const snapshot = () => 0;    // analogie pro starý render
```

**Zdroje (v tomto pořadí):**
1. **[javascript.info](https://javascript.info/)** — část „JavaScript Fundamentals" + „Closures" + „Promises, async/await". Nejlepší bezplatný hloubkový kurz. Closures: <https://javascript.info/closure>
2. **[MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript)** — referenční dokumentace na dohledání jednotlivých metod.

**Hotovo, když:** přečteš si [usePaginatedQuery.js](frontend/src/services/usePaginatedQuery.js) a rozumíš každému `...`, `?.`, `??`, `.map()`, `.filter()` — bez Reactu, jen jako JS.

---

## 3. Fáze 2 — React render model (🔴 přepóruj si základ)

**Proč:** komponenty chápeš, ale potřebuješ pevně **kdy a proč se komponenta překresluje**. Bez tohohle jsou hooky nepochopitelné.

Pochop těchto pět vět (a uměj je vysvětlit na [Nav.jsx](frontend/src/components/Nav/Nav.jsx)):
1. Komponenta je **funkce, která ze stavu a props vrací JSX**. Render = „zavolej tu funkci".
2. **Změna stavu (`setState`) → React zavolá funkci znovu** → spočítá nový JSX → porovná a updatne DOM.
3. Při každém renderu vznikají **nové lokální proměnné a nové funkce** (proto closures!).
4. **Props tečou dolů**, stav patří komponentě. Děti dostávají data + callbacky.
5. **Klíče (`key`) v seznamech** říkají Reactu, který prvek je který — `key={ev.id}` [EventsPage.jsx:239](frontend/src/pages/Events/EventsPage.jsx#L239).

**Zdroje:**
- **[react.dev → Learn](https://react.dev/learn)** — oficiální, výborně napsané. Projdi: „Describing the UI", „Adding Interactivity", „Thinking in React".
- Konkrétně: **[State as a Snapshot](https://react.dev/learn/state-as-a-snapshot)** a **[Render and Commit](https://react.dev/learn/render-and-commit)** — přesně řeší, co ti chybí.

**Hotovo, když:** umíš na papíře vysvětlit, co se stane krok za krokem, když v [Nav.jsx](frontend/src/components/Nav/Nav.jsx) klikneš na hamburger a `setMenuOpen` přepne stav.

---

## 4. Fáze 3 — Hooky do hloubky (🔴 tvoje hlavní mezera)

Tady strav nejvíc času. Ber hook po hooku a vždy si najdi reálné použití v repu.

### 4.1 `useState` — lokální stav
- Kde: `const [menuOpen, setMenuOpen] = useState(false)` [Nav.jsx:26](frontend/src/components/Nav/Nav.jsx#L26)
- Pochop: **funkční update** `setMenuOpen((o) => !o)` (pracuje s nejnovější hodnotou) vs. `setMenuOpen(!menuOpen)` (může být zastaralé).

### 4.2 `useEffect` — synchronizace s vnějškem ⭐ nejtěžší
**Není to lifecycle metoda.** Je to: „po renderu udrž tuhle vnější věc v souladu se stavem; když se závislosti změní, ukliď po starém a nastav nové."

Tři části, všechny vidíš v [Nav.jsx:36-56](frontend/src/components/Nav/Nav.jsx#L36-L56):
```js
useEffect(() => {
  const onScroll = () => { /* ... */ };
  window.addEventListener('scroll', onScroll);   // setup
  return () => window.removeEventListener('scroll', onScroll); // cleanup
}, []);                                            // dependency array
```
- **Dependency array** `[]` = jen po mountu; `[location.pathname]` = po každé změně cesty [Nav.jsx:60](frontend/src/components/Nav/Nav.jsx#L60); chybějící = po každém renderu (skoro nikdy nechceš).
- **Cleanup funkce** (`return () => ...`) je povinná všude, kde se něco „přihlašuje" — listener, `setTimeout`, observer, subscription. Bez ní memory leak. Viz debounce v [EventsPage.jsx:46-49](frontend/src/pages/Events/EventsPage.jsx#L46-L49): `return () => clearTimeout(t)`.
- **StrictMode v devu spouští efekty dvakrát** ([main.jsx:16](frontend/src/main.jsx#L16)) — schválně, aby odhalil chybějící cleanup. Až tě to zmate, je to tohle.
- **`cancelled` flag** pattern v [queryCache.js:174](frontend/src/services/queryCache.js#L174) — brání zápisu stavu po odmountování. Naučit se nazpaměť.

⭐ **Povinné čtení:** [Dan Abramov — A Complete Guide to useEffect](https://overreacted.io/a-complete-guide-to-useeffect/). Po něm `useEffect` přestane být magie.
A oficiální [You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect) — kdy efekt NEpoužívat.

### 4.3 `useRef` — dvě různá použití (časté nedorozumění)
1. **Odkaz na DOM uzel:** `ref={navRef}` → `navRef.current.contains(...)` [Nav.jsx:96](frontend/src/components/Nav/Nav.jsx#L96).
2. **Měnitelná hodnota, která přežije render a NEspouští překreslení:** `lastY`, `upRef` [Nav.jsx:28-29](frontend/src/components/Nav/Nav.jsx#L28-L29), `reqIdRef` [usePaginatedQuery.js:44](frontend/src/services/usePaginatedQuery.js#L44), `fetcherRef` [queryCache.js:165](frontend/src/services/queryCache.js#L165).

Pravidlo: **`useState` když změna má překreslit UI; `useRef` když si jen potřebuješ něco pamatovat napříč rendery bez překreslení.** `fetcherRef.current = fetcher` je trik „drž nejnovější funkci, ať ji nemusím dávat do dependencies".

### 4.4 `useCallback` a `useMemo` — referenční stabilita
- **Problém:** každý render vyrobí novou funkci/objekt. Když ji dáš do dependency array efektu nebo do `memo` dítěte, „změní se" pokaždé → smyčka / zbytečné překreslení.
- **`useCallback`** zmrazí identitu funkce: `buildParams` [EventsPage.jsx:52-58](frontend/src/pages/Events/EventsPage.jsx#L52-L58) se přepočítá jen když se změní `city/season/debouncedQuery`.
- **`useMemo`** zmrazí výsledek výpočtu: `cacheKey` [EventsPage.jsx:62-65](frontend/src/pages/Events/EventsPage.jsx#L62-L65), třídění `upcoming/past` [EventsPage.jsx:113-120](frontend/src/pages/Events/EventsPage.jsx#L113-L120).
- **Nepřeoptimalizuj:** používá se účelně tam, kde hodnota jde do dependencies nebo do těžkého výpočtu. Ne na každou proměnnou.

### 4.5 `useContext` — globální stav bez „prop drillingu"
- `const { user, isAdmin, logout } = useAuth()` [EventsPage.jsx:21](frontend/src/pages/Events/EventsPage.jsx#L21).
- `useAuth` je vlastní wrapper nad `useContext(AuthContext)` [AuthContext.jsx:88-92](frontend/src/context/AuthContext.jsx#L88-L92). Provider obaluje appku v [main.jsx:20](frontend/src/main.jsx#L20).
- Pochop tok: `AuthProvider` drží `user` ve `useState`, dá ho do `value`, kterýkoliv potomek si ho přečte přes `useAuth()`.

### 4.6 Vlastní hooky + Pravidla hooků
- **Vlastní hook = funkce začínající `use`, která volá jiné hooky.** Sdílí *logiku*, ne stav.
- Studuj [useReveal.js](frontend/src/hooks/useReveal.js) — kombinuje `useState`, `useRef`, `useCallback` a **callback ref** (`ref` je funkce, ne `useRef` objekt — připojí observer přesně když prvek vznikne v DOM). Tohle je pokročilé; vrať se k němu po 4.1–4.5.
- **Pravidla hooků** (ESLint je hlídá): volej je jen na nejvyšší úrovni komponenty/hooku, nikdy v `if`/cyklu/po `return`. Proč: React je páruje podle pořadí volání.

**Zdroje:**
- **[react.dev → Reference → Hooks](https://react.dev/reference/react/hooks)** — referenční stránka ke každému hooku má skvělé příklady a „Pitfalls".
- **[react.dev → Reusing Logic with Custom Hooks](https://react.dev/learn/reusing-logic-with-custom-hooks)**
- Video (volitelně): „useEffect" a „useRef" epizody na kanálu **Jack Herrington** nebo **Web Dev Simplified**.

**Hotovo, když:** přečteš [usePaginatedQuery.js](frontend/src/services/usePaginatedQuery.js) celé a rozumíš, proč tam je `reqIdRef`, proč `useMemo` kolem `items` a co dělá `useEffect` na řádku 56.

---

## 5. Fáze 4 — Datová vrstva projektu (🟠 tady ti pomůže Django)

Tohle je nejchytřejší část kódu a zároveň místo, kde tvoje **Django znalost je výhoda** — je to hranice mezi React klientem a tvým DRF backendem.

### 5.1 Axios + API hranice — [api.js](frontend/src/services/api.js)
- `axios.create({ baseURL: '/api', withCredentials: ... })` — jedna instance pro celou appku.
- **Request interceptor** [api.js:22-36](frontend/src/services/api.js#L22-L36): web posílá CSRF cookie (`X-CSRFToken`), nativní app posílá `Authorization: Token ...`. Tohle přímo navazuje na tvoje Django session vs. DRF token auth.
- **Response interceptor** [api.js:44-64](frontend/src/services/api.js#L44-L64): na `401` (vypršelá session) přesměruje na `/prihlasit`. Pochop výjimku „AUTH_PROBE_PATHS", aby se neredirectovalo při běžném ověřování hosta.
- Dole jsou **tenké funkce na endpointy** (`fetchEvents`, `toggleRsvp`, …) — tohle voláš z komponent. Když přidáš endpoint v Django, přidáš sem jeho dvojče.

### 5.2 Vlastní query cache — [queryCache.js](frontend/src/services/queryCache.js)
Ručně napsaný **stale-while-revalidate** cache. Nejlépe ho pochopíš, když si přečteš dokumentaci knihovny, kterou napodobuje, abys znal **pojmenování konceptů**:

> **Přečti si koncepty [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview)** — „query keys", „stale time", „caching", „invalidation". Nepoužíváte ji, ale `queryCache.js` dělá *přesně tyhle věci ručně*. Jakmile znáš slovník, kód je čitelný.

Co pochopit v tomto souboru:
- **`cache` Map** (key → {value, fetchedAt}) + **TTL** z [config.js](frontend/src/constants/config.js) → „fresh / stale / vyhodit".
- **In-flight deduplikace** [queryCache.js:94-105](frontend/src/services/queryCache.js#L94-L105) — dvě komponenty žádající stejný klíč dostanou jeden request.
- **Retry s backoffem** [queryCache.js:78-88](frontend/src/services/queryCache.js#L78-L88) — řeší „studený start" Render free tieru.
- **Pub/sub** (`subscribe`/`notify`) [queryCache.js:32-49](frontend/src/services/queryCache.js#L32-L49) — když se cache změní (login/logout → `clearCache`), všichni konzumenti se přerenderují.

### 5.3 `usePaginatedQuery` — [usePaginatedQuery.js](frontend/src/services/usePaginatedQuery.js)
Postavený nad `useCachedQuery`. První stránka v cache, „Načíst další" se nalepuje lokálně, změna filtru shodí lokální stránky. Použití: [EventsPage.jsx:67-78](frontend/src/pages/Events/EventsPage.jsx#L67-L78).

**Hotovo, když:** umíš popsat, co se stane od kliknutí na filtr města po zobrazení nových karet — přes `cacheKey` → `useCachedQuery` → `dedupedFetch` → `setEntry` → `notify` → překreslení.

---

## 6. Fáze 5 — Routing (🟠 React Router 7)

**Proč:** přidáváš/měníš stránky, čteš parametry z URL, řešíš odkazy.

| Co | Kde |
|---|---|
| `BrowserRouter` obaluje appku | [main.jsx:17](frontend/src/main.jsx#L17) |
| `Routes` + `Route path=... element=...` | [App.jsx:61-81](frontend/src/App.jsx#L61-L81) |
| **Dynamické segmenty** `:slug`, `:username` | [App.jsx:65-67](frontend/src/App.jsx#L65-L67) |
| `useParams()` — čtení segmentu | v page komponentách (např. EventDetail) |
| `useLocation()` — aktuální cesta | [Nav.jsx:23](frontend/src/components/Nav/Nav.jsx#L23), [App.jsx:30](frontend/src/App.jsx#L30) |
| `Link` / `NavLink` (aktivní stav) | [Nav.jsx:107-116](frontend/src/components/Nav/Nav.jsx#L107-L116) |
| **Lazy + Suspense** (code splitting) | [App.jsx:11-27](frontend/src/App.jsx#L11-L27), [App.jsx:60](frontend/src/App.jsx#L60) |
| **Preload na hover** (vlastní trik) | [Nav.jsx:105](frontend/src/components/Nav/Nav.jsx#L105) → [routePreload.js](frontend/src/services/routePreload.js) |

Pochop hlavně **`lazy(() => import(...))` + `<Suspense fallback>`**: každá stránka je samostatný JS chunk stažený až při první návštěvě. Proto je úvodní načtení rychlé.

**Zdroj:** **[React Router — oficiální dokumentace](https://reactrouter.com/)** (sekce „Routing", „Navigating"). Pozor: hledej **v7**, ne staré v5/v6 tutoriály — API se měnilo.

**Hotovo, když:** umíš přidat novou stránku: vytvořit `pages/Neco/NecoPage.jsx`, přidat `lazy()` import a `<Route>` v [App.jsx](frontend/src/App.jsx).

---

## 7. Fáze 6 — CSS a styling (🔴 tvoje 5/10, povinné zlepšení)

**Proč:** většina každodenních úprav je vizuálních. Projekt **nepoužívá žádný CSS framework** — je to ruční moderní CSS. To je vlastně dobře: naučíš se to „pořádně".

### Konvence v tomhle projektu
- **Design tokeny** (barvy, fonty, mezery, stíny) jako CSS proměnné v [colors_and_type.css](frontend/src/styles/colors_and_type.css). **Vždy používej proměnné** (`var(--gol-pink)`), ne natvrdo `#e15463`.
- **CSS na komponentu**: vedle `Nav.jsx` je [Nav.css](frontend/src/components/Nav/Nav.css), importované přímo (`import './Nav.css'`). Žádné CSS Modules, žádný scoping — třídy jsou globální, proto prefixované (`nav-`, `ev-`, `fp-`).
- Globální základ: [global.css](frontend/src/styles/global.css), [page-bg.css](frontend/src/styles/page-bg.css), [reveal.css](frontend/src/styles/reveal.css).

### Co se naučit (v tomto pořadí)
1. **Box model, cascade, specificita** — proč „můj styl nezabírá". Základ všeho.
2. **Custom properties (CSS proměnné)** — `--x: ...; color: var(--x)`. Srdce design systému tady.
3. **Flexbox** — řádky/sloupce, zarovnání (nav, karty, filtry).
4. **Grid** — `events-grid` mřížky karet [EventsPage.jsx:237](frontend/src/pages/Events/EventsPage.jsx#L237).
5. **Responsivita** — `@media`, `clamp()`, mobile-first.
6. **Transitions/transforms** — `hidden` třída navu, hover efekty.
7. **Pozicování** (`absolute/sticky/fixed`, `z-index`) — sticky nav, vrstvy grain/stage.

**Zdroje (CSS je nejlíp přes interaktivní průvodce):**
- **[web.dev → Learn CSS](https://web.dev/learn/css/)** — moderní, strukturované, od Googlu.
- **[CSS-Tricks — A Complete Guide to Flexbox](https://css-tricks.com/snippets/css/a-guide-to-flexbox/)** a **[…to Grid](https://css-tricks.com/snippets/css/complete-guide-grid/)** — referenční taháky, měj otevřené při práci.
- **[Josh Comeau — CSS resources](https://www.joshwcomeau.com/)** (blog) — výborná vysvětlení specificity, flexboxu, stacking contextu.
- Procvičení: **[Flexbox Froggy](https://flexboxfroggy.com/)** a **[Grid Garden](https://cssgridgarden.com/)** (hry, hodina každá).

**Hotovo, když:** dokážeš v [EventCard.css](frontend/src/components/EventCard) změnit rozložení karty a odůvodnit každou property — a používáš `var(--...)` tokeny.

---

## 8. Fáze 7 — Build a prostředí (🟡 Vite)

**Proč:** občas potřebuješ rozjet dev, pochopit proč „funguje to lokálně, ale jinak na produkci", přidat proměnnou.

- **Dev server + proxy:** [vite.config.js](frontend/vite.config.js) přesměrovává `/api`, `/media`, `/admin` na `http://localhost:8000` (tvoje Django). **Takhle běží React a Django vedle sebe v devu** — React na Vite (typicky `:5173`), volání `/api/...` proxy pošle na Django. Na produkci Django servíruje hotový build a `/api` je same-origin.
- **Env proměnné:** `import.meta.env.VITE_API_URL`, `import.meta.env.DEV` [api.js:16](frontend/src/services/api.js#L16), [AuthContext.jsx:60](frontend/src/context/AuthContext.jsx#L60). Jen proměnné s prefixem `VITE_` se dostanou do klienta.
- **Módy:** `--mode mobile` pro Capacitor build ([package.json](frontend/package.json) skripty `build:mobile`).
- **npm skripty:** `npm run dev` (s autogenerací obrázků přes `predev`), `npm run build`, `npm test`.
- **Obrázkový pipeline:** `scripts/optimize-images.js` (sharp) generuje WebP — viz tvoje paměťová poznámka o `image-src/` → `public/img/`.

**Zdroj:** **[Vite — Guide](https://vitejs.dev/guide/)** (sekce „Env Variables and Modes", „Dev Server Proxy"). Krátké, čti jen co potřebuješ.

**Hotovo, když:** rozjedeš `npm run dev` + Django na `:8000` současně a chápeš, proč request na `/api/events/` skončí v Django.

---

## 9. Fáze 8 — Mobil: Capacitor (🟡 jen když saháš na appku)

**Proč:** appka je tatáž React SPA zabalená do nativního webview. Většinu času ji řešit nemusíš, ale pár míst v kódu se chová jinak podle platformy.

- **Co je Capacitor:** vezme `dist/` build a spustí ho ve WKWebView (iOS) / WebView (Android) + most k nativním API.
- **Detekce platformy:** [platform.js](frontend/src/services/platform.js) → `isNative`. Větví se podle ní auth (token vs cookie) a chování v [api.js](frontend/src/services/api.js), [AuthContext.jsx](frontend/src/context/AuthContext.jsx), [main.jsx:33](frontend/src/main.jsx#L33).
- **Nativní pluginy** (z `package.json`): Geolocation (check-in na eventu), Share, Calendar, Preferences (úložiště tokenu), StatusBar, SplashScreen.
- **Most do nativu:** [NativeBridge](frontend/src/components/NativeBridge/NativeBridge).

**Zdroj:** **[Capacitor — Docs](https://capacitorjs.com/docs)** (jen „Basics" + plugin, který zrovna řešíš). Nech na později.

---

## 10. Fáze 9 — Testy (🟡 Vitest + Testing Library)

**Proč:** až budeš upravovat logiku (cache, utils), test ji ohlídá.

- Stack: **Vitest** (běhové prostředí, jako Jest) + **@testing-library/react** (renderování a dotazování komponent jako uživatel).
- Existující vzory ke kopírování: [queryCache.test.js](frontend/src/services/queryCache.test.js), [errors.test.js](frontend/src/services/errors.test.js), [ToastProvider.test.jsx](frontend/src/components/Toast/ToastProvider.test.jsx).
- Spuštění: `npm test` (watch) / `npm run test:run` (jednorázově).
- Filozofie Testing Library: testuj **chování** (co vidí/dělá uživatel), ne implementaci.

**Zdroje:** **[Vitest](https://vitest.dev/)** + **[Testing Library — React](https://testing-library.com/docs/react-testing-library/intro/)**.

---

## 11. Tahák: vzory, které v tomhle repu uvidíš pořád

Jakmile rozpoznáš tyhle idiomy, kód čteš mnohem rychleji:

| Vzor | Co znamená | Příklad |
|---|---|---|
| **`cancelled` flag** | „neukládej stav po odmountování" | [queryCache.js:174-233](frontend/src/services/queryCache.js#L174-L233) |
| **`xxxRef.current = xxx`** | „drž nejnovější hodnotu mimo dependencies" | [queryCache.js:165-166](frontend/src/services/queryCache.js#L165-L166) |
| **`reqIdRef` / request id** | „zahoď výsledek staré asynchronní akce" | [usePaginatedQuery.js:44](frontend/src/services/usePaginatedQuery.js#L44) |
| **`cacheKey` jako string filtrů** | klíč cache odvozený z filtrů | [EventsPage.jsx:62-65](frontend/src/pages/Events/EventsPage.jsx#L62-L65) |
| **`extractX` funkce** | adaptér tvar odpovědi → lokální pole | [EventsPage.jsx:16-18](frontend/src/pages/Events/EventsPage.jsx#L16-L18) |
| **debounce přes `setTimeout` + cleanup** | nečekat na každý stisk klávesy | [EventsPage.jsx:46-49](frontend/src/pages/Events/EventsPage.jsx#L46-L49) |
| **preload na `onMouseEnter`** | přednačti chunk+data před kliknutím | [Nav.jsx:105](frontend/src/components/Nav/Nav.jsx#L105) |
| **imperativní `toast.success(...)`** | notifikace mimo React strom | [AuthContext.jsx:37](frontend/src/context/AuthContext.jsx#L37) |
| **reveal on scroll** `[ref, inView]` | animace při scrollu do view | [EventsPage.jsx:136](frontend/src/pages/Events/EventsPage.jsx#L136) |
| **lazy route + Suspense** | stránka = samostatný chunk | [App.jsx:11-27](frontend/src/App.jsx#L11-L27) |

---

## 12. Cvičení, které tě naučí tenhle kód nejrychleji

**Přečti jednu akci od začátku do konce.** Tohle je lepší než deset tutoriálů:

> **„Otevřu `/events`, napíšu do hledání ‚karaoke', kliknu na filtr města."**
>
> Projdi to soubory v tomto pořadí a u každého kroku si řekni *proč*:
> 1. URL `/events` → `<Route>` v [App.jsx:64](frontend/src/App.jsx#L64) → `lazy` import → `Suspense` fallback „Načítám…".
> 2. `EventsPage` se naroutuje → `useState` filtrů [EventsPage.jsx:22-28](frontend/src/pages/Events/EventsPage.jsx#L22-L28).
> 3. Psaní do hledání → `setQuery` → `useEffect` debounce [EventsPage.jsx:46](frontend/src/pages/Events/EventsPage.jsx#L46) → po 300 ms `setDebouncedQuery`.
> 4. Změna `debouncedQuery` → nový `cacheKey` ([:62](frontend/src/pages/Events/EventsPage.jsx#L62)) → `usePaginatedQuery` → `useCachedQuery` vidí nový klíč → `dedupedFetch` → `fetchEvents` ([api.js:107](frontend/src/services/api.js#L107)) → Axios → proxy → Django.
> 5. Odpověď → `setEntry` → `notify` → komponenta se překreslí → `.map()` vyrenderuje `EventCard`y.
> 6. Klik na město → `setCity` → znovu nový `cacheKey` → (a `handleSeasonChange` resetuje město, aby nevznikl prázdný výsledek).

Napiš si k tomu vlastní poznámky. Až to projdeš jednou, většina ostatních stránek je stejný vzor.

---

## 13. Doporučené pořadí a odhad času

Realistické tempo při práci/studiu vedle (uprav podle sebe):

| Týden | Fáze | Výsledek — co už zvládneš upravovat |
|---|---|---|
| 1 | Fáze 1 (JS) + Fáze 2 (render model) | čteš JS a JSX bez zadrhnutí |
| 2–3 | **Fáze 3 (hooky)** ⭐ | bezpečně měníš stav, efekty, handlery v komponentách |
| 4 | Fáze 6 (CSS) — paralelně klidně dřív | samostatně měníš vzhled a layout |
| 5 | Fáze 4 (data) + Fáze 5 (routing) | přidáš endpoint+stránku, chápeš cache |
| 6 | Fáze 7 (Vite) + Fáze 9 (testy), Fáze 8 dle potřeby | rozjedeš, otestuješ, nasadíš změnu |

**Nejdřív měň, pak chápej do hloubky.** Bezpečné první úpravy (vzestupně podle obtížnosti):
1. **Text/copy** v JSX (Czech labely) — nulové riziko.
2. **CSS** jedné komponenty (barvy, mezery přes tokeny).
3. **Nový filtr/tlačítko** na existující stránce (`useState` + handler).
4. **Nová stránka** (kopie vzoru + `<Route>`).
5. **Nový API endpoint** (Django + dvojče v [api.js](frontend/src/services/api.js) + napojení v page).
6. Až nakonec: zásah do [queryCache.js](frontend/src/services/queryCache.js) / [usePaginatedQuery.js](frontend/src/services/usePaginatedQuery.js).

---

## 14. Sbalený seznam zdrojů (od nejdůležitějších)

**React & hooky (priorita):**
- [react.dev/learn](https://react.dev/learn) — oficiální kurz (Learn + Reference)
- [Dan Abramov — A Complete Guide to useEffect](https://overreacted.io/a-complete-guide-to-useeffect/) ⭐
- [react.dev — You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect)

**JavaScript (prerekvizit):**
- [javascript.info](https://javascript.info/) — closures, promises, async
- [MDN JS reference](https://developer.mozilla.org/en-US/docs/Web/JavaScript)

**CSS (tvoje slabina):**
- [web.dev — Learn CSS](https://web.dev/learn/css/)
- [CSS-Tricks Flexbox](https://css-tricks.com/snippets/css/a-guide-to-flexbox/) + [Grid](https://css-tricks.com/snippets/css/complete-guide-grid/)
- [Flexbox Froggy](https://flexboxfroggy.com/) · [Grid Garden](https://cssgridgarden.com/)

**Ekosystém projektu:**
- [React Router v7](https://reactrouter.com/)
- [TanStack Query — koncepty](https://tanstack.com/query/latest) (pro pochopení `queryCache.js`)
- [Axios](https://axios-http.com/docs/intro)
- [Vite Guide](https://vitejs.dev/guide/)
- [Capacitor Docs](https://capacitorjs.com/docs)
- [Vitest](https://vitest.dev/) · [Testing Library](https://testing-library.com/docs/react-testing-library/intro/)

---

### TL;DR
Tvoje jediná opravdová bariéra je **JS closures/async → React render model → hooky** (Fáze 1–3). Dej do nich 2–3 týdny a 80 % kódu se otevře. CSS řeš paralelně (je to ruční moderní CSS, žádný framework). Datová vrstva ([queryCache.js](frontend/src/services/queryCache.js)) je nejchytřejší část — pochop ji přes slovník TanStack Query, ale sahej na ni až nakonec. Django ti dává náskok přesně na API hranici ([api.js](frontend/src/services/api.js)).
