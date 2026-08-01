import ChipSelect from '../../components/ChipSelect/ChipSelect';

/**
 * One Google Form question, drawn with the site's own inputs.
 *
 * This is the whole point of reading the form's structure instead of embedding
 * it: an iframe is cross-origin, so its fields can never take our CSS. Here
 * they are ordinary elements using the same classes as the event editor
 * (`gol-field` / `gol-input` / `gol-textarea` in styles/edit-form.css), so the
 * form matches the rest of the site by construction rather than by imitation.
 *
 * field  : {entry_id, label, help, type, required, options}
 * value  : string, or string[] for checkboxes
 * onChange(next)
 * error  : string — server-side complaint for this field
 */
export default function FormField({ field, value, onChange, error }) {
  const { entry_id: id, label, help, required } = field;
  const described = [help && `${id}-help`, error && `${id}-error`].filter(Boolean).join(' ');

  return (
    <div className={`gol-field gol-full signup-field${error ? ' has-error' : ''}`}>
      <label htmlFor={id}>
        <span>{label}{required && ' *'}</span>
      </label>
      {help && <p className="signup-field-help" id={`${id}-help`}>{help}</p>}

      <Control
        field={field}
        value={value}
        onChange={onChange}
        describedBy={described || undefined}
      />

      {error && <p className="signup-field-error" id={`${id}-error`} role="alert">{error}</p>}
    </div>
  );
}

function Control({ field, value, onChange, describedBy }) {
  const { entry_id: id, type, required, options } = field;
  const common = {
    id,
    'aria-describedby': describedBy,
    'aria-invalid': describedBy?.includes('-error') || undefined,
    required,
  };

  switch (type) {
    case 'long_text':
      return (
        <textarea
          {...common}
          className="gol-textarea"
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    case 'radio':
    case 'select':
      // Rendered as a chip row rather than a native <select>: the site has no
      // styled select, and these lists are short enough to show at once.
      return (
        <div className="signup-choices" role="radiogroup" aria-labelledby={id}>
          {options.map((opt) => (
            <button
              type="button"
              key={opt}
              className={`signup-choice${value === opt ? ' on' : ''}`}
              aria-pressed={value === opt}
              // Re-clicking clears an optional answer; a required one can only
              // be swapped, never emptied back to nothing.
              onClick={() => onChange(value === opt && !required ? '' : opt)}
            >
              {opt}
            </button>
          ))}
        </div>
      );

    case 'checkboxes':
      return (
        <ChipSelect
          options={options}
          selected={Array.isArray(value) ? value : []}
          onChange={onChange}
        />
      );

    case 'scale':
      // Same shape as the event feedback rating, so a 1–10 question reads the
      // way ratings already read on this site.
      return (
        <div className="signup-scale" role="radiogroup" aria-labelledby={id}>
          {options.map((opt) => (
            <button
              type="button"
              key={opt}
              className={`signup-scale-dot${value === opt ? ' on' : ''}`}
              aria-pressed={value === opt}
              onClick={() => onChange(opt)}
            >
              {opt}
            </button>
          ))}
        </div>
      );

    case 'date':
    case 'time':
      return (
        <input
          {...common}
          className="gol-input"
          type={type}
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    default:
      return (
        <input
          {...common}
          className="gol-input"
          type="text"
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}
