import { Link } from 'react-router-dom';
import './Button.css';

/**
 * Unified button — renders as <button>, <a>, or <Link> depending on `as`.
 *
 * variant : 'nav' | 'action' | 'ghost' | 'frost'   (default: 'nav')
 *   nav    — home-page 3D filled button, for links that navigate somewhere
 *   action — round filled pill, for performing an action (submit, RSVP, share)
 *   ghost  — round outline, for secondary / back / cancel
 *   frost  — nav's 3D shape with a frosted translucent-black surface (dark CTA)
 * size    : 'sm' | 'md' | 'lg'            (default: 'md')
 * as      : 'button' | 'a' | 'link'       (default: 'button')
 */
export default function Button({
  variant = 'nav',
  size = 'md',
  as = 'button',
  to,
  href,
  disabled = false,
  busy = false,
  className = '',
  children,
  onClick,
  type = 'button',
  ...rest
}) {
  const classes = [
    'btn',
    `btn-${variant}`,
    `btn-${size}`,
    className,
  ].filter(Boolean).join(' ');

  const content = (
    <>
      {busy && <span className="btn-spinner" aria-hidden="true" />}
      {children}
    </>
  );

  if (as === 'link' && to) {
    return (
      <Link to={to} className={classes} aria-disabled={disabled || undefined} {...rest}>
        {content}
      </Link>
    );
  }

  if (as === 'a') {
    return (
      <a href={href} className={classes} {...rest}>
        {content}
      </a>
    );
  }

  return (
    <button type={type} className={classes} disabled={disabled || busy} onClick={onClick} {...rest}>
      {content}
    </button>
  );
}
