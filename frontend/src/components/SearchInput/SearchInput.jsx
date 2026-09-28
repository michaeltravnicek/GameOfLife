import './SearchInput.css';

/**
 * Glass pill search field with a ⌕ glyph. One look everywhere — the skin is
 * the shared glass in shared-ui.css.
 */
export default function SearchInput({
  value,
  onChange,
  placeholder = 'Vyhledat…',
  className = '',
}) {
  const classes = ['search-wrap', className].filter(Boolean).join(' ');
  return (
    <div className={classes}>
      <input
        type="search"
        className="search-input"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete="off"
      />
    </div>
  );
}
