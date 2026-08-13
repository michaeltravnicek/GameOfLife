import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import NotFoundPage from './NotFoundPage';
import { QUIPS } from './quips';

const renderAt = () => render(
  <MemoryRouter initialEntries={['/tohle-neexistuje']}>
    <NotFoundPage />
  </MemoryRouter>,
);

describe('NotFoundPage', () => {
  it('names itself as a 404 and offers the way back', () => {
    renderAt();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/neexistuje/i);
    expect(screen.getByText('— Stránka nenalezena —')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /zpět na hlavní stránku/i })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /projít akce/i })).toHaveAttribute('href', '/events');
  });

  it('shows exactly one of the quips', () => {
    renderAt();
    expect(QUIPS.filter((q) => screen.queryByText(q))).toHaveLength(1);
  });

  it('can reach the last quip — the picker covers the whole list', () => {
    // Math.random() returns [0,1), so 0.999… must land on the final entry. An
    // off-by-one here would quietly make one line unreachable forever.
    vi.spyOn(Math, 'random').mockReturnValue(0.999999);
    renderAt();
    expect(screen.getByText(QUIPS[QUIPS.length - 1])).toBeInTheDocument();
  });
});

afterEach(() => vi.restoreAllMocks());
