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

_(zatím prázdné)_

---

## ✅ Hotovo (jen pro přehled, neřešit)
- [x] **Privacy flagy se vynucují na BE** (`leaderboard/privacy.py`, `visibility_for`) —
  `profile_payload` sekce podle flagů **vynechává**, ne nuluje, a posílá `hidden: [...]`,
  ať FE pozná „skryto" od „nemá nic". Přepínač `hide_pts` je v UI
  ([EditProfilePage.jsx](frontend/src/pages/Profile/EditProfilePage.jsx), sekce Soukromí).
- [x] **Lajky fotek napojené.** `setPhotoLike` má volajícího: srdíčko v mřížce galerie
  i v lightboxu, optimistické s rollbackem. Payload galerie posílá `id`, `like_count`
  a `liked_by_me`; oficiální fotky akcí mají `id: null` (lajkovat jdou jen fotky od lidí).
- [x] **Otázky na profilu.** `ProfileQuestion`/`ProfileAnswer` mají endpoint
  (`/api/v1/profile-questions/`), sekci v editaci profilu a výpis v „O mně".
  Otázky se píšou v Django adminu — dokud tam žádná není, sekce se nezobrazuje.
- [x] **Mazání účtu funguje.** `DELETE /api/v1/auth/me/delete/`; osobní údaje a nahrané
  soubory zmizí, body a účast zůstanou anonymně (viz zásady ochrany údajů, bod 6).
- [x] **Změna hesla** pro přihlášené: sekce „08 · Heslo" v editaci profilu.

## ✅ Hotovo v BE-first fázi (jen pro přehled, neřešit)
- [x] **Admin: správa účasti a bodů u akce.** `api.js` má `fetchEventAttendees`,
  `setEventAttendeePoints` (PUT), `removeEventAttendee` (DELETE), `fetchEventRsvps`.
  UI nakonec **žije přímo na detailu akce** ([EventDetailPage.jsx](frontend/src/pages/EventDetail/EventDetailPage.jsx))
  jako admin-only přepínač „Popis / Účast a body" — samostatná stránka
  `/sprava/akce/<slug>/ucast` nikdy nevznikla. Obsahuje: editaci bodů inline, přidání hráče (hledá v žebříčku,
  jen existující leaderboard-user), odebrání, filtr při >10 účastnících a
  seznam přihlášených s příznakem „nezapočítán".
- [x] **`attendee_count` na detailu akce.** Rekap u proběhlé akce ukazuje reálnou
  účast („X dorazilo"), ne `rsvp_count`; u nadcházející akce se `attendee_count`
  přidá k přihlášeným, jakmile někdo dorazí (check-in běží během akce).
- [x] API přesunuto pod `/api/v1/` — `api.js` baseURL + `.env.mobile` upravené.
- [x] RSVP a lajk: `toggleRsvp`→`setRsvp(slug, attending)`, `togglePhotoLike`→`setPhotoLike(photoId, liked)` (PUT/DELETE místo toggle POST).
- [x] `extractApiError` umí i holý DRF field-error tvar (`{field: [...]}`, `non_field_errors`).
