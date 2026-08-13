import './SearchInput.css';

export default function SearchInput({
  value,
  onChange,
  placeholder = 'Vyhledat…',
  className = '',
}) {
  return (
    <div className={`search-wrap${className ? ' ' + className : ''}`}>
      <input
        type="text"
        className="search-input"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete="off"
      />
    </div>
  );
}
