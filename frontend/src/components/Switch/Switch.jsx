import './Switch.css';

/**
 * Styled on/off toggle.
 *
 * checked  : bool
 * onChange : (next: bool) => void
 */
export default function Switch({ checked = false, onChange, id, ariaLabel, className = '' }) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={ariaLabel}
      className={`switch${checked ? ' on' : ''}${className ? ' ' + className : ''}`}
      onClick={() => onChange?.(!checked)}
    />
  );
}
