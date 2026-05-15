import { Link } from 'react-router-dom';
import './Footer.css';

export default function Footer() {
  return (
    <footer>
      <div className="ft-inner">
        <div className="ft-menu">
          <div className="ft-label">Menu</div>
          <Link className="ft-link" to="/">Domů</Link>
          <Link className="ft-link" to="/akce">Kalendář</Link>
          <Link className="ft-link" to="/galerie">Galerie</Link>
          <Link className="ft-link" to="/leaderboard">Leaderboard</Link>
          <a className="ft-link" style={{ marginTop: 14 }} href="#">Instagram</a>
          <a className="ft-link" href="#">Facebook</a>
          <a className="ft-link" href="#">TikTok</a>
        </div>
        <div className="ft-right">
          <div className="ft-logo"><span className="sp">✦</span> GAME OF LIFE</div>
          <p className="ft-desc">
            Game of Life sdružuje ty, co chtějí z každodenního stereotypu vytřískat maximum
            a nebojí se u toho jít do extrému i do hloubky. Jsme tvůj protijed na moderní izolaci.
          </p>
          <div className="ft-contact">Vojta Toman<br />+420 731 005 976</div>
          <div className="ft-credit">
            Tyhle krásný stránky vytvořil Michael Trávníček.
            <div className="ft-credit">
              Podílel se Lukáš Müller.
              <br />Game of Life © 2026
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
