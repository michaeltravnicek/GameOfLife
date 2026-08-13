import { useReveal } from '../../hooks/useReveal';

/**
 * Wraps content in an element that fades/staggers into view on scroll.
 * Convenient for mapped or multi-section markup where a per-item hook would
 * be awkward. Uses the shared `.reveal` / `.reveal-stagger` classes.
 *
 * as       : element type to render (default 'div')
 * stagger  : when true, direct children animate in sequence
 * className: extra classes merged onto the element
 */
export default function Reveal({ as: Tag = 'div', stagger = false, className = '', children, ...rest }) {
  const [ref, inView] = useReveal();
  const base = stagger ? 'reveal-stagger' : 'reveal';
  const cls = `${base}${inView ? ' in' : ''}${className ? ` ${className}` : ''}`;
  return (
    <Tag ref={ref} className={cls} {...rest}>
      {children}
    </Tag>
  );
}
