import './Stamp.css';

/**
 * Rubber-stamp mark — one design, two colourways and two sizes.
 *
 * Every stamp on the site is the same object: display type, all caps, a dashed
 * edge in the ink colour, a soft drop shadow, tilted off-axis. Only the colour
 * and the scale change, so a sticker on a card photo and the stamp that closes
 * a page read as the same thing.
 *
 * tone  : 'gold' (sticker on a photo or card corner) | 'pink' (closing stamp)
 * size  : 'sm' (default) | 'lg'
 * tilt  : degrees of rotation; each tone has its own default
 * arrow : appends the italic arrow the closing stamps carry
 */
export default function Stamp({
  tone = 'gold',
  size = 'sm',
  tilt,
  arrow = false,
  className = '',
  children,
  ...rest
}) {
  const style = tilt == null ? undefined : { '--stamp-tilt': `${tilt}deg` };
  const classes = ['gol-stamp', `gol-stamp--${tone}`, `gol-stamp--${size}`, className]
    .filter(Boolean)
    .join(' ');
  return (
    <span className={classes} style={style} {...rest}>
      {children}
      {arrow && <span className="gol-stamp-arrow" aria-hidden="true">→</span>}
    </span>
  );
}
