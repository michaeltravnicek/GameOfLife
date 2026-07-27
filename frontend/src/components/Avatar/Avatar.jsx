import { Link } from 'react-router-dom';
import { initials } from '../../utils/name';
import './Avatar.css';

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
    'u-mono',
    'avatar',
    `avatar-${size}`,
    rank ? `avatar-${rank}` : '',
    className,
  ].filter(Boolean).join(' ');

  const inner = photo
    ? <img src={photo} alt={name || ''} loading="lazy" />
    : initials(name, '');

  if (as === 'link' && to) {
    return <Link to={to} className={classes} style={style}>{inner}</Link>;
  }

  return <div className={classes} style={style}>{inner}</div>;
}
