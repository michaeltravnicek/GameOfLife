import './Badge.css';

/**
 * Small mono-italic uppercase pill — status, category, date, count. Pages
 * restyle its type and size through `className`, never its colours.
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
