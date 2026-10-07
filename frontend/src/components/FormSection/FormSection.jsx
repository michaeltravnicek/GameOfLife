// One numbered card of a poster form page (styles/edit-form.css): the dashed
// rule, then the card headed by its eyebrow, heading and italic sub-line. Each
// page sets the sub-line's cream level on `.gol-sec-sub`.
export default function FormSection({ eyebrow, heading, sub, cardClass, eyebrowClass, children }) {
  return (
    <section className="gol-section">
      <div className="gol-rule" />
      <div className={cardClass ? `gol-card ${cardClass}` : 'gol-card'}>
        <div className="gol-card-head">
          <div className={eyebrowClass ? `gol-sec-eyebrow ${eyebrowClass}` : 'gol-sec-eyebrow'}>{eyebrow}</div>
          <h2 className="gol-sec-heading">{heading}</h2>
          <p className="gol-sec-sub">{sub}</p>
        </div>
        {children}
      </div>
    </section>
  );
}
