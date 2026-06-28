import './PageHero.css';

/**
 * Shared page hero (eyebrow + H1 + optional tagline + dashed divider).
 *
 * Single source of truth for interior-page headers so top padding, the H1
 * scale, and the staggered entrance animation stay identical across pages.
 *
 * eyebrow  : node   — small label above the heading (gets ✦ flourishes)
 * title    : node   — main heading (string, or JSX for line breaks)
 * tagline  : node   — optional supporting sentence below the heading
 * divider  : bool   — show the dashed rule under the hero (default: true)
 * className: string — extra class on the <header> for page-specific tweaks
 */
export default function PageHero({
  eyebrow,
  title,
  tagline,
  divider = true,
  className = '',
}) {
  return (
    <header className={`page-hero ${className}`.trim()}>
      {eyebrow && <div className="page-hero-eyebrow">{eyebrow}</div>}
      {title && <h1 className="page-hero-title">{title}</h1>}
      {tagline && <p className="page-hero-tagline">{tagline}</p>}
    </header>
  );
}
