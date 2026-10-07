import PageStage from '../../components/PageStage/PageStage';
import './AuthPage.css';

// Shared look of all auth pages: photo bg + one opaque poster card holding the
// page name; inputs are mini homepage-event-card tickets (AuthPage.css).
export default function AuthShell({ title, sub, badge = false, children }) {
  return (
    <div className="auth-page has-stage">
      <PageStage image="gal12" position="center 30%" tint="alive" />

      <section className="auth-container">
        <div className="gol-card auth-card">
          {badge && (
            <img className="auth-badge" src="/img/GOL_C50_transparent.webp" alt="" width="126" height="126" />
          )}
          <div className="auth-card-inner">
            <div className="auth-card-tag">Game of Life · Sezóna 2025/26</div>
            <h2 className="auth-card-title">{title}</h2>
            <div className="auth-card-sub">{sub}</div>
            <div className="auth-divider" />
            {children}
          </div>
        </div>
      </section>
    </div>
  );
}
