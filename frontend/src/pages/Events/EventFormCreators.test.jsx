import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../services/api', () => ({
  createCategory: vi.fn(),
  createBadge: vi.fn(),
}));

import { createBadge, createCategory } from '../../services/api';
import { NewBadgeForm, NewCategoryForm } from './EventFormCreators';

describe('NewCategoryForm', () => {
  beforeEach(() => vi.clearAllMocks());

  it('stays collapsed until asked, so the picker keeps the focus', () => {
    render(<NewCategoryForm onCreated={vi.fn()} />);
    expect(screen.queryByLabelText('Název')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /nová kategorie/i })).toBeInTheDocument();
  });

  it('hands the created category back and closes', async () => {
    const user = userEvent.setup();
    createCategory.mockResolvedValue({ id: 7, name: 'Sport' });
    const onCreated = vi.fn();
    render(<NewCategoryForm onCreated={onCreated} />);

    await user.click(screen.getByRole('button', { name: /nová kategorie/i }));
    await user.type(screen.getByLabelText('Název'), 'Sport');
    await user.click(screen.getByRole('button', { name: 'Vytvořit kategorii' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith({ id: 7, name: 'Sport' }));
    expect(createCategory).toHaveBeenCalledWith('Sport');
    expect(screen.queryByLabelText('Název')).not.toBeInTheDocument();
  });

  it('shows the API error inline and keeps the panel open', async () => {
    const user = userEvent.setup();
    createCategory.mockRejectedValue({
      response: { data: { name: ['Kategorie s tímto názvem už existuje.'] } },
    });
    const onCreated = vi.fn();
    render(<NewCategoryForm onCreated={onCreated} />);

    await user.click(screen.getByRole('button', { name: /nová kategorie/i }));
    await user.type(screen.getByLabelText('Název'), 'Sport');
    await user.click(screen.getByRole('button', { name: 'Vytvořit kategorii' }));

    expect(await screen.findByText('Kategorie s tímto názvem už existuje.')).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
    // Still open: the typed name is what the author would have to retype.
    expect(screen.getByLabelText('Název')).toHaveValue('Sport');
  });

  it('refuses an empty name without calling the API', async () => {
    const user = userEvent.setup();
    render(<NewCategoryForm onCreated={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: /nová kategorie/i }));
    await user.click(screen.getByRole('button', { name: 'Vytvořit kategorii' }));

    expect(await screen.findByText('Zadej název kategorie.')).toBeInTheDocument();
    expect(createCategory).not.toHaveBeenCalled();
  });
});

describe('NewBadgeForm', () => {
  beforeEach(() => vi.clearAllMocks());

  it('posts multipart badge fields and hands the badge back', async () => {
    const user = userEvent.setup();
    createBadge.mockResolvedValue({ id: 3, name: 'Karaoke', image: null, image_scale: 1.4 });
    const onCreated = vi.fn();
    render(<NewBadgeForm onCreated={onCreated} />);

    await user.click(screen.getByRole('button', { name: /nový odznak/i }));
    await user.type(screen.getByLabelText(/^Název/), 'Karaoke');
    await user.clear(screen.getByLabelText(/^Zvětšení/));
    await user.type(screen.getByLabelText(/^Zvětšení/), '1.4');
    await user.click(screen.getByRole('button', { name: 'Vytvořit odznak' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    const fd = createBadge.mock.calls[0][0];
    expect(fd.get('name')).toBe('Karaoke');
    expect(fd.get('image_scale')).toBe('1.4');
    // No file picked — the badge is artwork-optional, so nothing is sent.
    expect(fd.get('image')).toBeNull();
  });
});
