import './DashedBorder.css';

/**
 * Two-tone dashed border overlay. Drops absolutely into any positioned parent.
 *
 * Matches the Figma pattern: a SOLID stroke painted underneath, with a DASHED
 * stroke (rounded caps) painted on top. The solid layer shows through the gaps
 * in the dashed layer, producing the "black dash / white gap" effect.
 *
 * baseColor  : color of the solid under-stroke    (default light)
 * dashColor  : color of the dashed top stroke     (default dark)
 * radius     : corner radius in px (match the parent's border-radius)
 * width      : stroke width — both layers use the same width so they align
 * dash / gap : dash and gap lengths in px
 */
export default function DashedBorder({
  baseColor = '#e8e8e8',
  dashColor = '#1d1d1d',
  radius = 14,
  width = 2,
  dash = 5,
  gap = 7,
  className = '',
}) {
  const dashArray = `${dash} ${gap}`;
  return (
    <svg
      className={`dashed-border${className ? ` ${className}` : ''}`}
      aria-hidden="true"
      focusable="false"
    >
      <rect
        width="100%"
        height="100%"
        rx={radius}
        ry={radius}
        fill="none"
        stroke={baseColor}
        strokeWidth={width}
      />
      <rect
        width="100%"
        height="100%"
        rx={radius}
        ry={radius}
        fill="none"
        stroke={dashColor}
        strokeWidth={width}
        strokeDasharray={dashArray}
        strokeLinecap="round"
      />
    </svg>
  );
}
