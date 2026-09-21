import './SearchInput.css';

/**
 * Dashed-pill search field with a ⌕ glyph.
 *
 * variant : 'default' | 'frost' — frost is the denser, darker skin for a field
 *           that sits directly on the photo stage (leaderboard toolbar) rather
 *           than inside a card.
 */
export default function SearchInput({
  value,
  onChange,
  placeholder = 'Vyhledat…',
  variant = 'default',
  className = '',
}) {
  const classes = ['search-wrap', variant === 'frost' && 'search-wrap--frost', className].filter(Boolean).join(' ');
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
