import { Link } from 'react-router-dom';
import Avatar from '../Avatar/Avatar';
import './PlayerRow.css';

// The row and its link helper belong together — every caller needs both.
// Splitting this out would only sharpen hot-reload granularity in dev.
// eslint-disable-next-line react-refresh/only-export-components
export function playerLink(p) {
  return p.profile_username ? `/profil/${p.profile_username}` : `/hrac/${p.id}`;
}

const TROPHIES = ['🏆', '🥈', '🥉'];

export default function PlayerRow({ player }) {
  const medal = player.rank <= 3 ? TROPHIES[player.rank - 1] : null;
  return (
    <Link to={playerLink(player)} className="player-row">
      <div className={`pr-rk${medal ? ' pr-rk-medal' : ''}`}>{medal || `${player.rank}.`}</div>
      <div className="pr-nm">
        {/* Photo for the medal ranks only, initials for everyone else — the same
            `rank <= 3` cut the trophy uses. Photos scattered through the whole
            list made arbitrary rows jump out; kept to the top three they read as
            part of the podium treatment rather than noise. */}
        <Avatar name={player.name} photo={medal ? player.photo : null} size="xs" />
        <span className="pr-txt">{player.name}</span>
      </div>
      <div className="pr-pt">{player.total_points}</div>
    </Link>
  );
}
