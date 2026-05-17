import { Link } from 'react-router-dom';
import './StartPlayingButton.css';

export default function StartPlayingButton({ to = '/registrace', className = '', children = 'Start Playing ➤', ...rest }) {
  const cls = `start-playing-btn${className ? ` ${className}` : ''}`;
  return (
    <Link to={to} className={cls} {...rest}>
      {children}
    </Link>
  );
}
