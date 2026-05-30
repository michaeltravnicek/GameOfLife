import { useState } from 'react';
import './FormInput.css';

/**
 * Styled form input with label.
 *
 * rightSlot : node — optional element rendered top-right of the label (e.g. a "Forgot password?" link)
 * error     : bool — applies error border styling
 *
 * When `type="password"`, the input grows a built-in show/hide toggle button
 * on the trailing edge that swaps the type between password / text.
 */
export default function FormInput({
  id,
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  error = false,
  required = false,
  autoComplete,
  rightSlot,
  className = '',
}) {
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === 'password';
  const inputType = isPassword && revealed ? 'text' : type;

  return (
    <div className={`form-field${className ? ' ' + className : ''}`}>
      {label && (
        <div className="form-field-label">
          <label htmlFor={id} className="form-field-label-text">
            {label}{required && ' *'}
          </label>
          {rightSlot}
        </div>
      )}
      <div className={`form-field-input-wrap${isPassword ? ' has-toggle' : ''}`}>
        <input
          id={id}
          type={inputType}
          className={`form-field-input${error ? ' has-error' : ''}`}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          required={required}
          autoComplete={autoComplete}
        />
        {isPassword && (
          <button
            type="button"
            className="form-field-pw-toggle"
            onClick={() => setRevealed((r) => !r)}
            aria-label={revealed ? 'Skrýt heslo' : 'Zobrazit heslo'}
            aria-pressed={revealed}
            tabIndex={-1}
          >
            {revealed ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
                <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
                <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
                <line x1="2" y1="2" x2="22" y2="22" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
