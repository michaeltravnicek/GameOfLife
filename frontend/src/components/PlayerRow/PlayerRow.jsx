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
        <Avatar name={player.name} photo={player.photo} size="xs" />
        <span className="pr-txt">{player.name}</span>
      </div>
      <div className="pr-pt">{player.total_points}</div>
    </Link>
  );
}
