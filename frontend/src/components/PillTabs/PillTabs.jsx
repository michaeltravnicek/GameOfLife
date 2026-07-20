import { useLayoutEffect, useRef, useState } from 'react';
import './PillTabs.css';

/**
 * Pill tab group with an animated sliding indicator behind the active tab.
 *
 * tabs     : Array<{ key: string, label: ReactNode, badge?: ReactNode }>
 * active   : string  — key of the active tab
 * onChange : (key) => void
 */
export default function PillTabs({ tabs, active, onChange, className = '' }) {
  const groupRef = useRef(null);
  const [indicator, setIndicator] = useState({ left: 5, width: 0, visible: false });

  useLayoutEffect(() => {
    const group = groupRef.current;
    if (!group) return undefined;
    const measure = () => {
      const activeBtn = group.querySelector('.pilltabs-btn.on');
      if (!activeBtn) {
        setIndicator((i) => ({ ...i, visible: false }));
        return;
      }
      const g = group.getBoundingClientRect();
      const a = activeBtn.getBoundingClientRect();
      setIndicator({ left: a.left - g.left, width: a.width, visible: true });
    };
    measure();
    window.addEventListener('resize', measure);

    // The first measure runs on the fallback font, so the indicator keeps the
    // pre-swap width (a few px too wide) until something forces a resize.
    // Re-measure once the webfonts land.
    let cancelled = false;
    document.fonts?.ready.then(() => { if (!cancelled) measure(); });

    return () => {
      cancelled = true;
      window.removeEventListener('resize', measure);
    };
  }, [active, tabs]);

  // After the hooks so the hook order stays stable across renders.
  if (!tabs || tabs.length === 0) return null;

  return (
    <div
      ref={groupRef}
      className={`pilltabs${indicator.visible ? ' has-active' : ''}${className ? ' ' + className : ''}`}
      style={{ '--pill-left': `${indicator.left}px`, '--pill-w': `${indicator.width}px` }}
    >
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          className={`pilltabs-btn${active === t.key ? ' on' : ''}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}
          {t.badge != null && <span className="pilltabs-badge">{t.badge}</span>}
        </button>
      ))}
    </div>
  );
}
