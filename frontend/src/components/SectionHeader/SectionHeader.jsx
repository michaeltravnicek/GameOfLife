import './SectionHeader.css';

/**
 * Section heading with optional dashed rule and eyebrow label — the one
 * section heading on the site; pages do not style their own.
 *
 * eyebrow : node    — small label above heading (e.g. "01 · Popis")
 * meta    : node    — quiet note on the eyebrow's right edge ("+120 pts na cestě")
 * heading : node    — main heading; use <span className="pink"> for an accent word
 * rule    : bool    — show dashed rule above eyebrow (default: true)
 * size    : 'md' | 'sm'  (default: 'md')
 * onPhoto : bool    — heading sits on the photo stage, not in a card: adds a
 *                     shadow so it stays legible
 * as      : 'h2' | 'h3'  (default: 'h2')
 */
export default function SectionHeader({
  eyebrow,
  meta,
  heading,
  rule = true,
  size = 'md',
  onPhoto = false,
  as: Tag = 'h2',
  className = '',
}) {
  return (
    <div className={className || undefined}>
      {rule && <div className="gol-rule" />}
      {eyebrow && (
        <div className={`u-label gol-sec-eyebrow sec-hdr-eyebrow${meta ? ' sec-hdr-eyebrow--meta' : ''}`}>
          <span>{eyebrow}</span>
          {meta && <span className="sec-hdr-meta">{meta}</span>}
        </div>
      )}
      {heading && (
        <Tag className={`sec-hdr-heading sec-hdr-heading-${size}${onPhoto ? ' sec-hdr-heading--on-photo' : ''}`}>{heading}</Tag>
      )}
    </div>
  );
}
