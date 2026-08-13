/**
 * The 404 page's one-liners. Its own module for two reasons: the page file then
 * exports only its component (fast refresh needs that), and adding a line here
 * never means opening the component at all.
 *
 * Add freely. The only rules are that it stays one sentence — it sits under a
 * huge 404 and competes with nothing — and that it explains *something*, so the
 * page is still useful to someone who genuinely mistyped an address.
 */
export const QUIPS = [
  'Jsi tu příliš brzo, tuhle akci jsme ještě nezačali plánovat.',
  'Prohledali jsme kalendář, žebříček i . Nic.',
  'Odkaz vede do prázdna. Stává se to i těm nejlepším.',
  'Fotky v galerii by tě mohli bavit víc',
];

/** One line at random. Kept out of the component so render stays pure. */
export function pickQuip() {
  return QUIPS[Math.floor(Math.random() * QUIPS.length)];
}
