import { useState } from 'react';
import Button from '../../components/Button/Button';
import { pickQuip } from './quips';
import './NotFoundPage.css';

/**
 * The catch-all route (`path="*"` in App.jsx).
 *
 * Django hands index.html to any path it doesn't own (mysite/views.py:react_index),
 * so every typo, dead link and stale bookmark lands in the SPA router. Without a
 * page here <Routes> matches nothing and renders an empty <main> under the nav —
 * which reads as a broken site rather than a wrong address.
 */
export default function NotFoundPage() {
  // Lazy initialiser, so the line is drawn once per mount rather than on every
  // render — and drawn outside render, which keeps the component pure.
  const [quip] = useState(pickQuip);

  return (
    <div className="notfound-page">
      <div className="nf-stage" aria-hidden="true" />
      <div className="gol-page-grain" aria-hidden="true" />

      <div className="nf-body">
        <div className="nf-code" aria-hidden="true">404</div>

        <div className="u-label nf-eyebrow">— Stránka nenalezena —</div>
        <h1 className="nf-title">Tahle akce <span className="pink">neexistuje.</span></h1>
        <p className="nf-tagline">{quip}</p>

        <div className="nf-actions">
          <Button as="link" to="/" variant="frost">← Zpět na hlavní stránku</Button>
          <Button as="link" to="/events" variant="frost">Projít akce</Button>
        </div>
      </div>
    </div>
  );
}
