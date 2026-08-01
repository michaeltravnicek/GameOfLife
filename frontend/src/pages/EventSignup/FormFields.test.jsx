import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FormField from './FormFields';

const field = (over = {}) => ({
  entry_id: 'entry.1',
  label: 'Jméno a příjmení',
  help: '',
  type: 'short_text',
  required: true,
  options: [],
  ...over,
});

describe('FormField', () => {
  it('labels a text question and marks it required', () => {
    render(<FormField field={field()} value="" onChange={() => {}} />);
    expect(screen.getByText(/Jméno a příjmení/)).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeRequired();
  });

  it('reports typing back to the caller', async () => {
    const onChange = vi.fn();
    render(<FormField field={field()} value="" onChange={onChange} />);
    await userEvent.type(screen.getByRole('textbox'), 'M');
    expect(onChange).toHaveBeenCalledWith('M');
  });

  it('renders a paragraph question as a textarea', () => {
    render(<FormField field={field({ type: 'long_text' })} value="" onChange={() => {}} />);
    expect(screen.getByRole('textbox').tagName).toBe('TEXTAREA');
  });

  it('renders one button per choice and marks the picked one', () => {
    const f = field({ type: 'radio', options: ['Ano', 'Ne'] });
    render(<FormField field={f} value="Ano" onChange={() => {}} />);
    expect(screen.getByRole('button', { name: 'Ano' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Ne' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('picks a choice on click', async () => {
    const onChange = vi.fn();
    const f = field({ type: 'radio', options: ['Ano', 'Ne'] });
    render(<FormField field={f} value="" onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Ne' }));
    expect(onChange).toHaveBeenCalledWith('Ne');
  });

  // A required question can be swapped but never emptied back to nothing.
  it('does not let a required choice be cleared by re-clicking', async () => {
    const onChange = vi.fn();
    const f = field({ type: 'radio', options: ['Ano', 'Ne'], required: true });
    render(<FormField field={f} value="Ano" onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Ano' }));
    expect(onChange).toHaveBeenCalledWith('Ano');
  });

  it('lets an optional choice be cleared by re-clicking', async () => {
    const onChange = vi.fn();
    const f = field({ type: 'radio', options: ['Ano', 'Ne'], required: false });
    render(<FormField field={f} value="Ano" onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Ano' }));
    expect(onChange).toHaveBeenCalledWith('');
  });

  it('renders every step of a scale question', () => {
    const f = field({ type: 'scale', options: ['1', '2', '3'] });
    render(<FormField field={f} value="2" onChange={() => {}} />);
    expect(screen.getAllByRole('button')).toHaveLength(3);
    expect(screen.getByRole('button', { name: '2' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows a server-side error and links it to the input', () => {
    render(
      <FormField field={field()} value="" onChange={() => {}} error="Toto pole je povinné." />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Toto pole je povinné.');
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows the question help text when there is one', () => {
    render(<FormField field={field({ help: 'Bez předvolby' })} value="" onChange={() => {}} />);
    expect(screen.getByText('Bez předvolby')).toBeInTheDocument();
  });
});
