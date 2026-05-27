import { Link } from 'react-router-dom';
import Avatar from '../Avatar/Avatar';
import './PlayerRow.css';

export function playerLink(p) {
  return p.profile_username ? `/profil/${p.profile_username}` : `/hrac/${p.id}`;
}

export default function PlayerRow({ player }) {
  return (
    <Link to={playerLink(player)} className="player-row">
      <div className="pr-rk">{player.rank}.</div>
      <div className="pr-nm">
        <Avatar name={player.name} photo={player.photo} size="xs" />
        <span className="pr-txt">{player.name}</span>
      </div>
      <div className="pr-pt">{player.total_points}<span className="pr-u">pts</span></div>
    </Link>
  );
}
