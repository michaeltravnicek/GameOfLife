import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PageState from './PageState';

describe('PageState', () => {
  it('announces loading politely and shows the spinner', () => {
    const { container } = render(<PageState kind="loading" text="Načítám akce…" />);
    expect(screen.getByRole('status')).toHaveTextContent('Načítám akce…');
    expect(container.querySelector('.gol-spinner')).not.toBeNull();
  });

  it('renders an empty state without a retry button', () => {
    render(<PageState kind="empty" text="Žádné akce." onRetry={() => {}} />);
    expect(screen.getByRole('status')).toHaveTextContent('Žádné akce.');
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('is an alert with a working retry when something failed', async () => {
    const onRetry = vi.fn();
    render(<PageState kind="error" text="Nepodařilo se načíst." onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nepodařilo se načíst.');
    await userEvent.click(screen.getByRole('button', { name: 'Zkusit znovu' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('disables the retry and swaps its label while busy', () => {
    render(<PageState kind="error" text="Chyba." onRetry={() => {}} busy />);
    const btn = screen.getByRole('button', { name: 'Načítám…' });
    expect(btn).toBeDisabled();
  });

  it('takes the compact and fill modifiers', () => {
    const { container } = render(<PageState kind="empty" text="x" compact fill />);
    const el = container.firstChild;
    expect(el).toHaveClass('page-state--compact');
    expect(el).toHaveClass('page-state--fill');
  });
});
