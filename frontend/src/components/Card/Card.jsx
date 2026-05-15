import './Card.css';

/**
 * Base card container.
 *
 * variant   : 'dark' | 'frosted' | 'light' | 'info'   (default: 'dark')
 * texture   : 'blue' | 'brown' | 'light' | null        (default: null)
 * padding   : 'sm' | 'md' | 'lg' | null                (default: 'md')
 * bordered  : bool — adds inner dashed border inset (leaderboard style)
 * hoverable : bool — adds hover lift + pink border
 * as        : string — HTML tag to render (default: 'div')
 */
export default function Card({
  variant = 'dark',
  texture = null,
  padding = 'md',
  bordered = false,
  hoverable = false,
  as: Tag = 'div',
  className = '',
  children,
  style,
  ...rest
}) {
  const classes = [
    'card',
    `card-${variant}`,
    texture ? `card-tex-${texture}` : '',
    padding ? `card-pad-${padding}` : '',
    bordered ? 'card-bordered' : '',
    hoverable ? 'card-hoverable' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <Tag className={classes} style={style} {...rest}>
      {children}
    </Tag>
  );
}
