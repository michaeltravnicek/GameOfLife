/**
 * Props that make a non-button element (a photo tile, a figure) behave like a
 * button for keyboard and screen-reader users: focusable, announced as a
 * button, and activated by Enter or Space as well as click.
 *
 *   <figure {...pressable(() => open(i))}>
 */
export function pressable(onActivate) {
  return {
    role: 'button',
    tabIndex: 0,
    onClick: onActivate,
    onKeyDown: (e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      onActivate(e);
    },
  };
}
