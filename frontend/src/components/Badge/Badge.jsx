import './Badge.css';

/**
 * Small mono-italic uppercase pill — status, category, date, count.
 *
 * Replaces six page-local versions (.ev-pill ×2, .ev-cat, .ft-badge,
 * .ev-hidden-badge, .date-stamp) that were the same pill drawn six times.
 *
 * tone : 'cream' (default, frosted on a photo) | 'pink' | 'gold' | 'muted'
 *      | 'live' (solid pink, for "právě teď") | 'paper' (cream on a photo)
 * as   : element type (default 'span')
 */
export default function Badge({ tone = 'cream', as: Tag = 'span', className = '', children, ...rest }) {
  const classes = ['gol-badge', `gol-badge--${tone}`, className].filter(Boolean).join(' ');
  return (
    <Tag className={classes} {...rest}>
      {children}
    </Tag>
  );
}
