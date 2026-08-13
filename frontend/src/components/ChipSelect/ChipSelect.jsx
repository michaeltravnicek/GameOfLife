import './ChipSelect.css';

/**
 * Toggleable chip group with an optional max-selection cap.
 *
 * options  : Array<string>      — chip labels (also used as values)
 * selected : Array<string>      — currently selected values
 * onChange : (next: string[]) => void
 * max      : number             — optional cap; adding past it is ignored
 * emptyText: string             — note shown instead of an empty chip group
 */
export default function ChipSelect({ options, selected, onChange, max, className = '', emptyText = 'Zatím není z čeho vybírat.' }) {
  const toggle = (val) => {
    if (selected.includes(val)) {
      onChange(selected.filter((s) => s !== val));
    } else {
      if (max && selected.length >= max) return;
      onChange([...selected, val]);
    }
  };

  if (!options || options.length === 0) {
    return <div className="chips-empty">{emptyText}</div>;
  }

  return (
    <div className={`chips${className ? ' ' + className : ''}`}>
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          className={`chip${selected.includes(opt) ? ' on' : ''}`}
          aria-pressed={selected.includes(opt)}
          onClick={() => toggle(opt)}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
