import { Link } from 'react-router-dom';
import './Footer.css';

const INSTAGRAM_URL = import.meta.env.VITE_INSTAGRAM_URL;

export default function Footer() {
  return (
    <footer>
      <div className="ft-inner">
        <div className="ft-menu">
          <div className="ft-label">Menu</div>
          <Link className="ft-link" to="/">Home</Link>
          <Link className="ft-link" to="/events">Kalendář</Link>
          <Link className="ft-link" to="/galerie">Galerie</Link>
          <Link className="ft-link" to="/leaderboard">Leaderboard</Link>
          {/* Instagram: set VITE_INSTAGRAM_URL in frontend/.env.production once the
              handle is known; the link stays out until then. */}
          {INSTAGRAM_URL && <a className="ft-link ft-link--gap" href={INSTAGRAM_URL} target="_blank" rel="noopener noreferrer">Instagram</a>}
          <a className={`ft-link${INSTAGRAM_URL ? '' : ' ft-link--gap'}`} href="https://www.facebook.com/profile.php?id=61576755543429&sk=followers&locale=cs_CZ" target="_blank" rel="noopener noreferrer">Facebook</a>
          <a className="ft-link" href="https://www.tiktok.com/@gameofyolo" target="_blank" rel="noopener noreferrer">TikTok</a>
        </div>
        <div className="ft-right">
          <div className="ft-logo"><img className="ft-logo-img" src="/assets/gameoflive-onrender-com-english-us-by-html-to-design-free-version-0905-gol-logo-bw-1.svg" alt="" aria-hidden="true" /> GAME OF LIFE</div>
          <p className="ft-desc">
            Game of Life sdružuje ty, co chtějí z každodenního stereotypu vytřískat maximum
            a nebojí se u toho jít do extrému i do hloubky. Jsme tvůj protijed na moderní izolaci.
          </p>
          <div className="ft-contact">Vojta Toman<br />+420 731 005 976</div>
          <div className="ft-credit">
            Tyhle krásný stránky vytvořil Michael Trávníček.
            <br />Game of Life © 2026
          </div>
          {/* Sits with the logo block, not in the menu column: the menu is gone
              on phones and the policy has to be findable by someone who never
              signed up. */}
          <Link className="ft-link ft-policy" to="/ochrana-osobnich-udaju">Ochrana osobních údajů</Link>
        </div>
      </div>
    </footer>
  );
}
