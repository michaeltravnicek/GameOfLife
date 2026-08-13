import { describe, expect, it } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToastProvider, ToastBridge, toast } from './ToastProvider';

const wrap = (ui) => render(
  <ToastProvider>
    <ToastBridge />
    {ui}
  </ToastProvider>,
);

describe('ToastProvider', () => {
  it('renders a success toast with title and message', () => {
    wrap(null);
    act(() => {
      toast.success('Vše OK', { title: 'Hotovo' });
    });
    expect(screen.getByText('Vše OK')).toBeInTheDocument();
    expect(screen.getByText('Hotovo')).toBeInTheDocument();
  });

  it('sets aria-live="assertive" on error toasts only', () => {
    wrap(null);
    act(() => {
      toast.error('Chyba!');
      toast.success('Ok!');
    });
    const errorEl = screen.getByText('Chyba!').closest('.toast');
    const successEl = screen.getByText('Ok!').closest('.toast');
    expect(errorEl).toHaveAttribute('aria-live', 'assertive');
    expect(successEl).toHaveAttribute('aria-live', 'polite');
  });

  it('dismisses when close button is clicked', async () => {
    const user = userEvent.setup();
    wrap(null);
    act(() => {
      toast.info('Zpráva');
    });
    expect(screen.getByText('Zpráva')).toBeInTheDocument();
    await user.click(screen.getByLabelText('Zavřít'));
    expect(screen.queryByText('Zpráva')).not.toBeInTheDocument();
  });
});
