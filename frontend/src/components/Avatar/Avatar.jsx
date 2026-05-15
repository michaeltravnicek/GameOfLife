import { Link } from 'react-router-dom';
import './Avatar.css';

function getInitials(name) {
  return (name || '')
    .split(' ')
    .map((w) => w[0])
    .filter(Boolean)
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

/**
 * Circular avatar showing a photo or initials fallback.
 *
 * size  : 'xs' | 'sm' | 'md' | 'lg' | 'xl'   (default: 'md')
 * rank  : 'gold' | 'silver' | 'bronze' | null  — coloured border
 * as    : 'div' | 'link'                        (default: 'div')
 */
export default function Avatar({
  name,
  photo,
  size = 'md',
  rank,
  as = 'div',
  to,
  className = '',
  style,
}) {
  const classes = [
    'avatar',
    `avatar-${size}`,
    rank ? `avatar-${rank}` : '',
    className,
  ].filter(Boolean).join(' ');

  const inner = photo
    ? <img src={photo} alt={name || ''} loading="lazy" />
    : getInitials(name);

  if (as === 'link' && to) {
    return <Link to={to} className={classes} style={style}>{inner}</Link>;
  }

  return <div className={classes} style={style}>{inner}</div>;
}
