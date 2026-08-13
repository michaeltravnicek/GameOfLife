import { Link } from 'react-router-dom';
import './PrivacyPage.css';

// Keep in sync with PRIVACY_POLICY_VERSION in djangotutorial/mysite/settings.py.
// Each registration stores the version the user agreed to, so a material change
// here means bumping both and deciding whether existing users must re-confirm.
export const POLICY_VERSION = '2026-07-22';

export default function PrivacyPage() {
  return (
    <div className="privacy-page">
      <div className="privacy-stage" aria-hidden="true" />
      <section className="privacy-container">
        <header className="privacy-head">
          <div className="privacy-tag">Game of Life</div>
          <h1 className="privacy-title">Zásady ochrany osobních údajů</h1>
          <p className="privacy-meta">
            Verze {POLICY_VERSION} · účinné od 22. 7. 2026
          </p>
        </header>

        <div className="privacy-body">
          <div className="privacy-todo">
            <strong>Než tohle zveřejníš:</strong> doplň údaje označené
            <code> [DOPLNIT] </code> a nech text zkontrolovat někým, kdo dělá do
            práva. Tenhle dokument je poctivý věcný popis toho, co aplikace
            skutečně dělá s daty — ale není to právní poradenství.
          </div>

          <h2>1. Kdo zpracovává tvoje údaje</h2>
          <p>
            Správcem osobních údajů je <strong>[DOPLNIT: přesný název
            provozovatele]</strong>, IČO <strong>[DOPLNIT]</strong>, se sídlem{' '}
            <strong>[DOPLNIT]</strong>.
          </p>
          <p>
            Kontakt ve věcech osobních údajů: <strong>[DOPLNIT e-mail]</strong>,
            Vojta Toman, +420&nbsp;731&nbsp;005&nbsp;976.
          </p>
          <p>
            Pověřence pro ochranu osobních údajů nemáme jmenovaného — pro rozsah
            našeho zpracování ho zákon nevyžaduje.
          </p>

          <h2>2. Jaké údaje o tobě máme</h2>
          <table className="privacy-table">
            <thead>
              <tr><th>Údaj</th><th>Odkud pochází</th></tr>
            </thead>
            <tbody>
              <tr><td>Jméno a přezdívka</td><td>zadáš při registraci</td></tr>
              <tr><td>E-mail</td><td>zadáš při registraci</td></tr>
              <tr><td>Heslo</td><td>ukládáme jen jako nevratný otisk (hash), nikdy v čitelné podobě</td></tr>
              <tr><td>Profilová fotka, bio, město</td><td>volitelně vyplníš v profilu</td></tr>
              <tr><td>Odkazy na sociální sítě</td><td>volitelně vyplníš (Instagram, Strava, Spotify, TikTok)</td></tr>
              <tr><td>Účast na akcích a body</td><td>vzniká tím, že se akcí účastníš</td></tr>
              <tr><td>Přihlášky na akce a zpětná vazba</td><td>zadáš na webu nebo ve formuláři</td></tr>
              <tr><td>Fotky z akcí</td><td>pořizujeme na akcích, případně je nahraješ sám</td></tr>
              <tr><td>Poloha při check-inu</td><td>jen v okamžiku, kdy sám potvrdíš účast na místě; neukládáme souřadnice, pouze výsledek ověření</td></tr>
              <tr><td>IP adresa</td><td>zpracovává se krátkodobě kvůli ochraně proti útokům na přihlášení</td></tr>
            </tbody>
          </table>

          <h2>3. Proč to zpracováváme a na jakém právním základě</h2>

          <h3>a) Vedení účtu a žebříčku</h3>
          <p>
            Právní základ: <em>plnění smlouvy</em> (čl. 6 odst. 1 písm. b GDPR).
            Bez těchto údajů ti nemůžeme vést účet, přiřazovat body ani tě
            zobrazit v žebříčku. Tvoje jméno, přezdížka, body a účast na akcích
            jsou veřejně viditelné — v tom je celý smysl žebříčku.
          </p>

          <h3>b) Propojení účtu s body z akcí</h3>
          <p>
            Právní základ: <em>plnění smlouvy</em>. Body z akcí evidujeme podle
            údaje z formuláře k akci — dřív to bylo telefonní číslo, dnes e-mail,
            případně jméno. <strong>Telefonní čísla už nesbíráme a ta dříve
            uložená jsme z databáze smazali.</strong> E-mail
            <strong> nezveřejňujeme</strong>.
          </p>

          <h3>c) Fotky z akcí</h3>
          <p>
            Právní základ: <em>souhlas</em> (čl. 6 odst. 1 písm. a GDPR) a u
            fotek, kde jsi rozpoznatelný, také ochrana osobnosti podle
            §&nbsp;84–90 občanského zákoníku.
          </p>
          <p>
            Pokud si nepřeješ být na konkrétní fotce, napiš nám a fotku
            odstraníme nebo tě z ní odstraníme. Nemusíš to nijak zdůvodňovat.
          </p>

          <h3>d) Bezpečnost</h3>
          <p>
            Právní základ: <em>oprávněný zájem</em> (čl. 6 odst. 1 písm. f
            GDPR). Krátkodobě zpracováváme IP adresy, abychom zabránili
            hádání hesel a zahlcení webu.
          </p>

          <h2>4. Jak dlouho údaje uchováváme</h2>
          <ul>
            <li><strong>Údaje účtu</strong> — po dobu existence účtu.</li>
            <li><strong>Body a účast na akcích</strong> — i po smazání účtu, ale v anonymizované podobě (viz bod 6).</li>
            <li><strong>Fotky</strong> — do odvolání souhlasu nebo do žádosti o odstranění.</li>
            <li><strong>Záznamy o nezdařených přihlášeních</strong> — 1 hodina.</li>
            <li><strong>Technické chybové záznamy</strong> — 30 dní.</li>
          </ul>

          <h2>5. Komu údaje předáváme</h2>
          <p>Nikomu je neprodáváme. Používáme tyto zpracovatele:</p>
          <table className="privacy-table">
            <thead>
              <tr><th>Služba</th><th>K čemu</th><th>Kde</th></tr>
            </thead>
            <tbody>
              <tr><td>Render</td><td>provoz webu a databáze</td><td>[DOPLNIT: region]</td></tr>
              <tr><td>Cloudflare</td><td>zrychlení a ochrana webu</td><td>globální síť</td></tr>
              <tr><td>Sentry</td><td>záznam technických chyb</td><td>EU (Frankfurt)</td></tr>
              <tr><td>Google Sheets</td><td>evidence účasti a bodů z akcí</td><td>mimo EU (USA)</td></tr>
              <tr><td>[DOPLNIT: e-mailová služba]</td><td>odesílání e-mailů (obnova hesla)</td><td>[DOPLNIT]</td></tr>
            </tbody>
          </table>
          <p>
            Sentry nastavujeme tak, aby k chybovým hlášením{' '}
            <strong>nepřipojoval</strong> tvoji identitu, cookies ani obsah
            odeslaných formulářů — dostává jen technický popis chyby.
          </p>
          <p>
            Předání do USA (Google) probíhá na základě standardních smluvních
            doložek podle čl. 46 GDPR.
          </p>

          <h2>6. Tvoje práva</h2>
          <p>Vůči svým údajům máš tato práva:</p>
          <ul>
            <li><strong>Na přístup</strong> — chtít kopii toho, co o tobě vedeme.</li>
            <li><strong>Na opravu</strong> — většinu si opravíš sám v profilu.</li>
            <li><strong>Na výmaz</strong> — viz níže.</li>
            <li><strong>Na omezení zpracování</strong> a <strong>na přenositelnost</strong> údajů.</li>
            <li><strong>Vznést námitku</strong> proti zpracování z oprávněného zájmu.</li>
            <li><strong>Odvolat souhlas</strong> (typicky u fotek), kdykoliv a bez udání důvodu. Odvolání nemá vliv na zpracování před odvoláním.</li>
          </ul>

          <h3>Jak funguje smazání účtu</h3>
          <p>
            Smažeme tvoje osobní údaje — jméno, přezdívku, e-mail, fotku, bio a
            odkazy na sítě. <strong>Body a záznam o účasti na
            akcích ale zůstanou v anonymizované podobě</strong>, bez vazby na
            tvoji osobu.
          </p>
          <p>
            Důvod: výsledky sezóny jsou společný záznam o proběhlých akcích a
            body ostatních hráčů dávají smysl jen v kontextu celkového pořadí.
            Po anonymizaci už ta data nejsou osobními údaji, protože tě podle
            nich nelze identifikovat.
          </p>

          <h2>7. Cookies</h2>
          <p>
            Používáme pouze <strong>technicky nezbytné</strong> cookies: jednu
            pro přihlášení (session) a jednu pro ochranu formulářů (CSRF). Bez
            nich by se nedalo přihlásit.
          </p>
          <p>
            Takové cookies nevyžadují souhlas a proto tě neotravujeme cookie
            lištou. <strong>Nepoužíváme</strong> analytiku ani reklamní nebo
            sledovací cookies.
          </p>

          <h2>8. Zabezpečení</h2>
          <ul>
            <li>Veškerá komunikace jde přes šifrované HTTPS.</li>
            <li>Hesla ukládáme jen jako nevratný otisk.</li>
            <li>Přihlašování je chráněné proti hádání hesel.</li>
            <li>Nahrávané obrázky se kontrolují a přepočítávají.</li>
          </ul>

          <h2>9. Stížnost</h2>
          <p>
            Pokud máš pocit, že s tvými údaji nenakládáme správně, ozvi se
            nejdřív nám — většinu věcí vyřešíme obratem. Máš ale i právo podat
            stížnost u dozorového úřadu:
          </p>
          <p>
            <strong>Úřad pro ochranu osobních údajů</strong><br />
            Pplk. Sochora 27, 170 00 Praha 7<br />
            <a href="https://www.uoou.cz" target="_blank" rel="noopener noreferrer">www.uoou.cz</a>
          </p>

          <h2>10. Změny</h2>
          <p>
            Zásady můžeme upravit. Každá verze má svoje číslo a datum (nahoře).
            U podstatných změn tě vyzveme k novému potvrzení při přihlášení.
          </p>
        </div>

        <div className="privacy-foot">
          <Link className="privacy-back" to="/registrace">← Zpět na registraci</Link>
        </div>
      </section>
    </div>
  );
}
