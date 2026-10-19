import styles from './forms.module.css'

interface Option<T extends string> {
  value: T
  label: string
}

interface SegmentedControlProps<T extends string> {
  name: string
  legend: string
  options: readonly Option<T>[]
  value: T
  onChange: (value: T) => void
  hint?: string
  hideLegend?: boolean
}

export function SegmentedControl<T extends string>({
  name,
  legend,
  options,
  value,
  onChange,
  hint,
  hideLegend = false,
}: SegmentedControlProps<T>) {
  return (
    <fieldset className={styles.fieldset}>
      <legend className={hideLegend ? 'visually-hidden' : styles.label}>{legend}</legend>
      <div className={styles.segmented}>
        {options.map((option) => (
          <label key={option.value} className={styles.segment}>
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
      {hint && <p className={styles.hint}>{hint}</p>}
    </fieldset>
  )
}
