import './FormInput.css';

/**
 * Styled form input with label.
 *
 * rightSlot : node — optional element rendered top-right of the label (e.g. a "Forgot password?" link)
 * error     : bool — applies error border styling
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
      <input
        id={id}
        type={type}
        className={`form-field-input${error ? ' has-error' : ''}`}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        autoComplete={autoComplete}
      />
    </div>
  );
}
