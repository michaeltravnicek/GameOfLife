import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoadMore from './LoadMore';

describe('LoadMore', () => {
  it('shows how many are left and loads more on click', async () => {
    const onClick = vi.fn();
    render(<LoadMore onClick={onClick} remaining={12} />);
    const btn = screen.getByRole('button', { name: 'Načíst další (12)' });
    await userEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('omits the count when it is unknown', () => {
    render(<LoadMore onClick={() => {}} />);
    expect(screen.getByRole('button', { name: 'Načíst další' })).toBeInTheDocument();
  });

  it('is disabled with a busy label while loading', () => {
    render(<LoadMore onClick={() => {}} busy remaining={3} />);
    expect(screen.getByRole('button', { name: 'Načítám…' })).toBeDisabled();
  });
});
