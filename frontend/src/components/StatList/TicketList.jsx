import StatList from './StatList';
import { TicketFrame } from '../DashedBorder/DashedBorder';

/**
 * A <StatList> wearing the ticket card: white dashed SVG frame with the dark
 * grain panel floating 7px inside it.
 *
 * This is the arrangement the profile page, player page and event-detail
 * attendance lists all share — the wrapper div + <TicketFrame /> + <StatList>
 * was copy-pasted on each of them. Every StatList prop is forwarded, so it is
 * a drop-in replacement for that trio.
 */
export default function TicketList({ className = '', ...statListProps }) {
  return (
    <div className="ticket-list">
      <TicketFrame />
      <StatList className={className} {...statListProps} />
    </div>
  );
}
