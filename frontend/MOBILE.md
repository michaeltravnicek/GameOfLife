# Mobilní aplikace (iOS + Android) — Capacitor

Mobilní aplikace je **stejná React SPA** zabalená do nativního obalu přes
[Capacitor](https://capacitorjs.com). Volá stejné API na Renderu jako web —
data jsou na jednom místě. Web build (`npm run build`, Render, WhiteNoise) se
nemění; mobil je paralelní build mód.

## Jak to funguje

- `npm run build:mobile` → Vite build s `--mode mobile`, načte [.env.mobile](.env.mobile)
  (`VITE_API_URL` míří na produkční API, `VITE_PUBLIC_WEB_URL` pro sdílené odkazy).
- `npx cap sync` zkopíruje `dist/` do nativních projektů `android/` a `ios/`.
- **Auth:** nativní aplikace nepoužívá session cookies (ve webview jsou
  nespolehlivé), ale DRF token — login/registrace pošle `client: "mobile"`,
  backend vrátí `token`, ten se ukládá do nativního úložiště
  (`@capacitor/preferences`) a posílá jako `Authorization: Token …`.
  Odhlášení token na serveru zneplatní.
- **Nativní funkce:** kalendář (`@ebarooni/capacitor-calendar` — tlačítko
  „Přidat do kalendáře" na detailu akce), geolokace pro check-in
  (`@capacitor/geolocation`), sdílení (`@capacitor/share`), splash + status
  bar, hardware back na Androidu, externí odkazy v systémovém prohlížeči.

## Android — lokální build (Linux)

### Prerekvizity (jednorázově)

```bash
sudo apt install openjdk-21-jdk          # Capacitor 8 vyžaduje JDK 21
# Android Studio (doporučeno) nebo cmdline-tools: https://developer.android.com/studio
# V SDK Manageru: Android SDK Platform 35 + Build-Tools + Platform-Tools (adb)
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
```

### Build a instalace

```bash
npm run cap:sync                          # build SPA + sync do android/
cd android && ./gradlew assembleDebug    # → app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Debug APK lze rovnou nainstalovat na telefon (povolit „instalace z neznámých
zdrojů"), bez Google Play účtu. Případně `npm run cap:android` otevře/spustí
emulátor přes Capacitor CLI.

### Vydání na Google Play (až bude účet — $25 jednorázově)

```bash
keytool -genkey -v -keystore gol-release.keystore -alias gol -keyalg RSA -keysize 2048 -validity 10000
cd android && ./gradlew bundleRelease    # → .aab pro Play Console
```

Keystore **nikdy necommitovat** — uložit bezpečně mimo git (jeho ztráta =
nemožnost aktualizovat aplikaci).

## iOS

Build vyžaduje macOS/Xcode. Bez Macu:

- **CI ověření:** [.github/workflows/ios-build.yml](../.github/workflows/ios-build.yml)
  kompiluje iOS projekt na GitHub Actions (macOS runner) při každém pushi do
  `frontend/**` — projekt je trvale „zelený" a připravený.
- **Publikace (až bude Apple Developer účet — $99/rok):**
  1. V Apple Developer portálu vytvořit App ID `com.gameofyolo.app`,
     distribuční certifikát a provisioning profil.
  2. Certifikát + profil nahrát jako GitHub secrets a rozšířit workflow o
     `xcodebuild archive` + `-exportArchive` (nebo fastlane) → upload do
     TestFlight/App Store.
  3. Alternativa: cloudové služby jako Codemagic/Appflow mají hotové iOS
     signing pipeline.

## Vývoj proti lokálnímu Djangu (emulátor)

Vytvoř `.env.mobile-dev` (necommitovat):

```
VITE_API_URL=http://10.0.2.2:8000/api
VITE_PUBLIC_WEB_URL=http://10.0.2.2:8000
```

`10.0.2.2` je host počítač z pohledu Android emulátoru. Pak:

```bash
vite build --mode mobile-dev && npx cap sync android
```

a dočasně přidat do `capacitor.config.json`: `"server": {"cleartext": true}`
(HTTP bez TLS — **nevracet do gitu**). Django musí běžet na `0.0.0.0:8000`
a mít origin v `CORS_ALLOWED_ORIGINS` (řeší `CORS_EXTRA_ORIGINS` env).

## Backend (Render)

- Migrace `authtoken` proběhne automaticky (`build.sh` → `manage.py migrate`).
- Volitelný env var `CORS_EXTRA_ORIGINS` (default
  `capacitor://localhost,https://localhost` je zabudovaný v settings.py).

## Ikony a splash screen

Zdrojové soubory v [resources/](resources/) (generované z
`claudedesign/logos/GOL_main_logo_pink.png`). Po změně:

```bash
npx @capacitor/assets generate --ios --android \
  --iconBackgroundColor '#0a0604' --splashBackgroundColor '#0a0604' \
  --iconBackgroundColorDark '#0a0604' --splashBackgroundColorDark '#0a0604'
```

## Co zatím není (další fáze)

- **Push notifikace** — backend nemá FCM/APNs infrastrukturu; až se přidá,
  zvážit tokeny per zařízení místo jednoho DRF tokenu per uživatel.
- **Offline režim** — aplikace vyžaduje připojení (stejně jako web);
  `@capacitor/network` by levně přidal hlášku „Jsi offline".
