import { usePlanSelection } from '@/features/route-comparison/selection'
import { CheckpointDetail } from './CheckpointDetail'
import { CheckpointList } from './CheckpointList'
import styles from './CheckpointPanel.module.css'

export function CheckpointPanel() {
  const { plan, selectedRoute, selectedCheckpoint, selectCheckpoint } = usePlanSelection()
  return (
    <section className={styles.panel} aria-labelledby="checkpoint-heading">
      <header className={styles.header}>
        <h2 id="checkpoint-heading" className="eyebrow">
          Checkpoints · {selectedRoute.label}
        </h2>
        <span className={styles.count}>
          {selectedRoute.checkpoints.length} · every {plan.sampling_interval_miles} mi
        </span>
      </header>
      {selectedCheckpoint ? (
        <CheckpointDetail
          checkpoint={selectedCheckpoint}
          loadWeightLb={plan.load_weight_lb}
          onClose={() => selectCheckpoint(null)}
        />
      ) : (
        <p className={styles.prompt}>
          Select a checkpoint on the map or in the list to see the forecast and why it received its
          classification.
        </p>
      )}
      <CheckpointList
        checkpoints={selectedRoute.checkpoints}
        selectedId={selectedCheckpoint?.id ?? null}
        onSelect={selectCheckpoint}
      />
    </section>
  )
}
