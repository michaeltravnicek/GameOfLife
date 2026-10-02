import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { pressable } from './a11y';

describe('pressable', () => {
  it('activates on Enter and Space pressed on the element itself', () => {
    const onActivate = vi.fn();
    render(<div {...pressable(onActivate)}>tile</div>);
    const tile = screen.getByRole('button', { name: 'tile' });
    fireEvent.keyDown(tile, { key: 'Enter' });
    fireEvent.keyDown(tile, { key: ' ' });
    fireEvent.keyDown(tile, { key: 'a' });
    expect(onActivate).toHaveBeenCalledTimes(2);
  });

  it('leaves Enter on a nested button to that button', () => {
    const onActivate = vi.fn();
    render(
      <div {...pressable(onActivate)}>
        <button type="button">like</button>
      </div>,
    );
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
    screen.getByText('like').dispatchEvent(event);
    expect(onActivate).not.toHaveBeenCalled();
    // Cancelling it would stop the browser turning Enter into the button's click.
    expect(event.defaultPrevented).toBe(false);
  });
});
