import './SectionHeader.css';

/**
 * Section heading with optional dashed rule and eyebrow label.
 *
 * eyebrow : string  — small label above heading (e.g. "— 01 · Popis —")
 * heading : string  — main heading text
 * rule    : bool    — show dashed rule above eyebrow (default: true)
 * size    : 'md' | 'sm'  (default: 'md')
 */
export default function SectionHeader({
  eyebrow,
  heading,
  rule = true,
  size = 'md',
  className = '',
}) {
  return (
    <div className={className || undefined}>
      {rule && <div className="sec-hdr-rule" />}
      {eyebrow && <div className="u-label sec-hdr-eyebrow">{eyebrow}</div>}
      {heading && (
        <h2 className={`sec-hdr-heading sec-hdr-heading-${size}`}>{heading}</h2>
      )}
    </div>
  );
}
