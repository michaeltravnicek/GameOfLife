# Frontend TODO — odložená FE práce (backend-first fáze)

> Provozní backlog: věci na **frontendu**, které vzniknou/čekají kvůli změnám na backendu.
> Teď se plně věnujeme BE; sem si odkládáme FE úkoly, ať se na nic nezapomene.
> Toto NENÍ učební roadmapa — ta je v [FRONTEND_ROADMAP.md](FRONTEND_ROADMAP.md).
> Formát: `[ ]` = čeká, `[x]` = hotovo. U každé položky endpoint/soubor + proč.

---

## 🟠 Střední — nové pole/chování na BE, FE ho zatím neukazuje

_(zatím prázdné)_

---

## ⚪ Odloženo — čeká na produktové rozhodnutí na BE

### Privacy flagy (`hide_pts`, `hide_events`, `members_only`)
Momentálně se **ukládají, ale nikde nevynucují** (viz komentář v `accounts/models.py`). Až se na BE rozhodne, co mají dělat, dodělat FE:
- [ ] Přidat přepínač **`hide_pts`** do [EditProfilePage.jsx](frontend/src/pages/Profile/EditProfilePage.jsx) — jako jediný ze tří ho v UI vůbec nemá.
- [ ] Až BE začne v `profile_payload` data vynechávat podle flagů, ošetřit na FE chybějící pole (např. `members_only` → stav „soukromý profil", `hide_events`/`hide_pts` → nezobrazovat sekci) — čti, co reálně přijde v odpovědi, ne co čekáš.
- Rozhodnutí „zapojit vs. vyhodit" zatím otevřené.

---

## 🟢 Drobnosti / až bude potřeba

- [ ] `setPhotoLike(photoId, liked)` v `api.js` existuje (PUT/DELETE, idempotentní), ale nemá zatím žádného volajícího — napojit, až přibude tlačítko lajku v galerii.

---

## ✅ Hotovo v BE-first fázi (jen pro přehled, neřešit)
- [x] **Admin: správa účasti a bodů u akce.** `api.js` má `fetchEventAttendees`,
  `setEventAttendeePoints` (PUT), `removeEventAttendee` (DELETE), `fetchEventRsvps`.
  UI je **samostatná admin stránka** `/sprava/akce/<slug>/ucast`
  ([EventAttendancePage.jsx](frontend/src/pages/Admin/EventAttendancePage.jsx)) —
  ne panel na detailu akce, aby detail zůstal veřejná stránka. Vypadá jako profil
  (poster hero + credits + `ticket-list`/`StatList`). Odkaz vede z back-stripu
  na detailu akce. Obsahuje: editaci bodů inline, přidání hráče (hledá v žebříčku,
  jen existující leaderboard-user), odebrání, filtr při >10 účastnících a
  seznam přihlášených s příznakem „nezapočítán".
- [x] **`attendee_count` na detailu akce.** Rekap u proběhlé akce ukazuje reálnou
  účast („X dorazilo"), ne `rsvp_count`; u nadcházející akce se `attendee_count`
  přidá k přihlášeným, jakmile někdo dorazí (check-in běží během akce).
- [x] API přesunuto pod `/api/v1/` — `api.js` baseURL + `.env.mobile` upravené.
- [x] RSVP a lajk: `toggleRsvp`→`setRsvp(slug, attending)`, `togglePhotoLike`→`setPhotoLike(photoId, liked)` (PUT/DELETE místo toggle POST).
- [x] `extractApiError` umí i holý DRF field-error tvar (`{field: [...]}`, `non_field_errors`).
