import TicketList from '../../components/StatList/TicketList';
import { EVENT_COLUMNS, EVENT_LIST_CLASS } from '../../components/StatList/eventColumns';
import { TicketFrame } from '../../components/DashedBorder/DashedBorder';
import PointsChart from './PointsChart';

// Shared building blocks for the two profile-style pages (ProfilePage and the
// anonymous PlayerPage). They render the identical poster credits, event lists
// and points/category views; only the section numbers differ (ProfilePage has
// an extra "O mně" section up front), hence the `startNum` prop. The per-season
// data these render is derived by the `useSeasonView` hook (useSeasonView.js).

const pad = (n) => String(n).padStart(2, '0');

/** The three poster credit blocks (Body / Akcí / Pozice). */
export function ProfileCredits({ st }) {
  return (
    <div className="credits">
      <span className="credits-rule" />
      <div className="credit">
        <div className="credit-label">— Body —</div>
        <div className="credit-value">{st.totalPts}</div>
        <div className="credit-sub"><strong>{st.cities.length} měst</strong> · {st.future.length ? 'aktivní sezóna' : 'sezóna ukončena'}</div>
      </div>
      <div className="credit">
        <div className="credit-label">— Akcí —</div>
        <div className="credit-value">{st.evs.length}</div>
        <div className="credit-sub"><strong>{st.past.length} absolv.</strong> · {st.future.length} nadch.</div>
      </div>
      <div className="credit">
        <div className="credit-label">— Pozice —</div>
        <div className="credit-value">{st.rank ? `#${st.rank}` : '—'}</div>
        <div className="credit-sub">{st.rank ? 'v sezóně' : 'zatím bez bodů'}</div>
      </div>
    </div>
  );
}

/** "Nadcházející" (startNum) + "Absolvované" (startNum+1) event lists. */
export function EventsSections({ st, upcoming, past, startNum }) {
  return (
    <>
      {upcoming.length > 0 && (
        <div className="section">
          <div className="sec-rule" />
          <div className="sec-eyebrow"><span>— {pad(startNum)} · Nadcházející —</span><span className="meta">+{st.futurePts} pts na cestě</span></div>
          <h2 className="sec-heading">Co ho <span className="pink">čeká.</span></h2>
          <TicketList
            className={EVENT_LIST_CLASS}
            columns={EVENT_COLUMNS}
            rows={upcoming}
            rowKey={(e) => e.slug}
            rowLink={(e) => `/events/${e.slug}`}
            rowClass={() => 'future'}
          />
        </div>
      )}

      <div className="section">
        <div className="sec-rule" />
        <div className="sec-eyebrow"><span>— {pad(startNum + 1)} · Absolvované —</span><span className="meta">+{st.pastPts} pts zatím</span></div>
        <h2 className="sec-heading">Co má <span className="pink">za sebou.</span></h2>
        <TicketList
          className={EVENT_LIST_CLASS}
          columns={EVENT_COLUMNS}
          rows={past}
          rowKey={(e) => e.slug}
          rowLink={(e) => `/events/${e.slug}`}
          rowClass={() => 'past'}
          emptyText="Zatím žádné absolvované akce v této sezóně."
        />
      </div>
    </>
  );
}

/** "Body v čase" chart (startNum) + "Kategorie" breakdown (startNum+1). */
export function PointsSections({ st, cats, today, startNum }) {
  return (
    <>
      <div className="section">
        <div className="sec-rule" />
        <div className="sec-eyebrow"><span>— {pad(startNum)} · Body v čase —</span><span className="meta">křivka sezóny</span></div>
        <h2 className="sec-heading">Křivka <span className="pink">sezóny.</span></h2>

        <div className="chart-card">
          <TicketFrame />
          <div className="chart-in">
            <div className="chart-meta">
              <div>
                <div className="l">Celkem v sezóně</div>
                <div className="total">{st.totalPts}<small>pts</small></div>
              </div>
              <div className="legend">
                <span><i />Absolvováno</span>
                <span><i className="dashed" />Nadcházející</span>
                <span style={{ color: '#f5c842' }}><i style={{ background: '#f5c842' }} />Dnes</span>
              </div>
            </div>
            <PointsChart stats={st} today={today} />
          </div>
        </div>
      </div>

      {cats.sorted.length > 0 && (
        <div className="section">
          <div className="sec-rule" />
          <div className="sec-eyebrow"><span>— {pad(startNum + 1)} · Kategorie —</span><span className="meta">{cats.sorted.length} kategorií</span></div>
          <h2 className="sec-heading">V čem <span className="pink">jede.</span></h2>
          <div className="cat-list">
            {cats.sorted.map(([cat, b]) => (
              <div className="cat-row" key={cat}>
                <span className="name">{cat}</span>
                <span className="bar"><i style={{ width: `${Math.round((b.p / cats.max) * 100)}%` }} /></span>
                <span className="meta">{b.n}× · <b>+{b.p}</b></span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
