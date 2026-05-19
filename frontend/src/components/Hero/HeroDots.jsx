import './HeroDots.css';

/**
 * Bottom-centered dot indicator for the Hero slideshow.
 *
 * count   : total number of slides
 * current : index of the active slide
 * onChange(index): called when the user clicks/keys a dot
 */
export default function HeroDots({ count = 0, current = 0, onChange }) {
  if (count < 2) return null;
  return (
    <div className="gol-hero-dots">
      {Array.from({ length: count }).map((_, i) => (
        <span
          key={i}
          role="button"
          aria-label={`Slide ${i + 1}`}
          aria-pressed={i === current}
          tabIndex={0}
          className={`gol-hero-dots__dot${i === current ? ' is-active' : ''}`}
          onClick={() => onChange?.(i)}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onChange?.(i)}
        />
      ))}
    </div>
  );
}
