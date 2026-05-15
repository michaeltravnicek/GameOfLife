import './TabBar.css';

/**
 * Frosted-glass pill tab group.
 *
 * tabs     : Array<{ key: string, label: string }>
 * active   : string   — key of the active tab
 * onChange : (key: string) => void
 */
export default function TabBar({ tabs, active, onChange, className = '' }) {
  return (
    <div className={`tabs-bar${className ? ' ' + className : ''}`}>
      {tabs.map((t) => (
        <button
          key={t.key}
          className={`tabs-bar-btn${active === t.key ? ' active' : ''}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
