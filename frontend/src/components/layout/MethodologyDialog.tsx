import type { Ref } from 'react'
import styles from './MethodologyDialog.module.css'

export function MethodologyDialog({ ref }: { ref: Ref<HTMLDialogElement> }) {
  return (
    <dialog ref={ref} className={styles.dialog} aria-labelledby="methodology-title">
      <form method="dialog" className={styles.header}>
        <h2 id="methodology-title">How routes are assessed</h2>
        <button type="submit" className={styles.close} aria-label="Close methodology">
          ×
        </button>
      </form>
      <div className={styles.body}>
        <section>
          <h3>Checkpoints and arrival times</h3>
          <p>
            Checkpoints are placed every 10, 25 or 50 miles measured along each route, plus the
            origin and destination. Each checkpoint's ETA comes from the routing provider's
            per-segment drive times added to your departure time. It then represents the road
            halfway to its neighbours, so mileage totals do not depend on the sampling interval.
          </p>
        </section>
        <section>
          <h3>Weather at each checkpoint</h3>
          <p>
            Wind is the sustained 10 m forecast at the hour nearest the ETA. Rain and snow are the
            mean intensity over the forecast hour containing the ETA (that hour's accumulation);
            short bursts can be heavier. Gusts are shown but not classified.
          </p>
        </section>
        <section>
          <h3>Risk thresholds</h3>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col" />
                <th scope="col">Low</th>
                <th scope="col">Moderate</th>
                <th scope="col">High</th>
                <th scope="col">Severe</th>
                <th scope="col">No Travel</th>
              </tr>
            </thead>
            <tbody className="numeric">
              <tr>
                <th scope="row">Wind mph</th>
                <td>&lt;25</td>
                <td>25–&lt;35</td>
                <td>35–&lt;45</td>
                <td>45–&lt;55</td>
                <td>≥55</td>
              </tr>
              <tr>
                <th scope="row">Rain in/hr</th>
                <td>&lt;0.10</td>
                <td>0.10–&lt;0.25</td>
                <td>0.25–&lt;0.50</td>
                <td>0.50–1.00</td>
                <td>&gt;1.00</td>
              </tr>
              <tr>
                <th scope="row">Snow in/hr</th>
                <td>&lt;0.5</td>
                <td>0.5–&lt;1.0</td>
                <td>1.0–&lt;2.0</td>
                <td>2.0–3.0</td>
                <td>&gt;3.0</td>
              </tr>
            </tbody>
          </table>
          <p>
            Load rules: wind 45–&lt;55 mph with a load over 30,000 lb is No Travel; wind 35–&lt;45 mph
            with a load over 40,000 lb is Severe. A checkpoint takes the highest level of any
            measure.
          </p>
        </section>
        <section>
          <h3>Ranking</h3>
          <p>
            Routes with complete forecasts and no No Travel segment rank first, then routes with
            incomplete forecasts (below 95% coverage), then routes with a No Travel segment. Within
            each group: fewest Severe-or-worse miles, then fewest High miles, then lowest average
            risk (mile-weighted, Low = 0 to No Travel = 4), then shortest drive time.
          </p>
          <p>
            Missing forecasts are never treated as low risk. This is a weather screening tool: the
            truck profile accounts for weight only, so confirm routes for height, hazmat, permits and
            local restrictions.
          </p>
        </section>
      </div>
    </dialog>
  )
}
