import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import PageStage from './PageStage';

describe('PageStage', () => {
  it('points the stage at the mobile and desktop variants of the image', () => {
    const { container } = render(<PageStage image="gal1" position="center 15%" tint="alive" grain="blue" />);
    const stage = container.querySelector('.page-stage');
    expect(stage).toHaveClass('page-stage--alive');
    expect(stage).toHaveAttribute('aria-hidden', 'true');
    const css = stage.getAttribute('style');
    expect(css).toContain('--stage-m: url(/img/gal1-mobile.webp)');
    expect(css).toContain('--stage-d: url(/img/gal1-desktop.webp)');
    expect(css).toContain('--stage-pos: center 15%');
    expect(container.querySelector('.page-grain')).toHaveClass('page-grain--blue');
  });

  it('defaults to the calm tint with brown grain, and can drop the grain', () => {
    const { container, rerender } = render(<PageStage image="gal2" />);
    expect(container.querySelector('.page-stage')).toHaveClass('page-stage--calm');
    expect(container.querySelector('.page-grain')).toHaveClass('page-grain--brown');
    rerender(<PageStage image="gal2" grain="none" />);
    expect(container.querySelector('.page-grain')).toBeNull();
  });
});
