import { type KeyboardEvent, useId, useState } from 'react'
import formStyles from '@/components/forms/forms.module.css'
import type { GeocodeResult } from '../api/schemas'
import { useLocationSuggestions } from '../hooks/useLocationSuggestions'
import type { LocationValue } from '../schemas/plan-form'
import styles from './LocationField.module.css'

interface LocationFieldProps {
  id: string
  label: string
  value: LocationValue
  onChange: (value: LocationValue) => void
  onBlur: () => void
  error?: string | undefined
  placeholder?: string
}

/**
 * Accessible combobox (WAI-ARIA 1.2 list autocomplete). Choosing a
 * suggestion pins its coordinates; editing the text clears them so the
 * server geocodes whatever was typed.
 */
export function LocationField({
  id,
  label,
  value,
  onChange,
  onBlur,
  error,
  placeholder,
}: LocationFieldProps) {
  const listId = useId()
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const pinned = value.lat !== undefined
  const suggestions = useLocationSuggestions(value.query, open && !pinned)
  const results = open && !pinned ? (suggestions.data ?? []) : []
  const showList = results.length > 0

  const choose = (result: GeocodeResult) => {
    onChange({ query: result.label, lat: result.lat, lon: result.lon })
    setOpen(false)
    setActiveIndex(-1)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' && results.length > 0) {
      event.preventDefault()
      setOpen(true)
      setActiveIndex((index) => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp' && results.length > 0) {
      event.preventDefault()
      setActiveIndex((index) => (index <= 0 ? results.length - 1 : index - 1))
    } else if (event.key === 'Enter' && showList && activeIndex >= 0) {
      event.preventDefault()
      const result = results[activeIndex]
      if (result) choose(result)
    } else if (event.key === 'Escape') {
      setOpen(false)
      setActiveIndex(-1)
    }
  }

  const describedBy = [error ? `${id}-error` : null, `${id}-status`].filter(Boolean).join(' ')

  return (
    <div className={formStyles.field}>
      <label htmlFor={id} className={formStyles.label}>
        {label}
      </label>
      <div className={styles.wrapper}>
        <input
          id={id}
          className={formStyles.input}
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={listId}
          aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          placeholder={placeholder}
          value={value.query}
          onChange={(event) => {
            onChange({ query: event.target.value })
            setOpen(true)
            setActiveIndex(-1)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            setOpen(false)
            onBlur()
          }}
          onKeyDown={onKeyDown}
        />
        <ul id={listId} role="listbox" className={styles.list} hidden={!showList} aria-label={`${label} suggestions`}>
          {results.map((result, index) => (
            <li
              key={`${result.lat},${result.lon},${result.label}`}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              className={styles.option}
              onMouseDown={(event) => {
                event.preventDefault()
                choose(result)
              }}
            >
              {result.label}
            </li>
          ))}
        </ul>
      </div>
      {error && (
        <p id={`${id}-error`} className={formStyles.error} role="alert">
          {error}
        </p>
      )}
      <p id={`${id}-status`} className={formStyles.hint} aria-live="polite">
        {statusText(pinned, suggestions.isFetching, suggestions.isError)}
      </p>
    </div>
  )
}

function statusText(pinned: boolean, fetching: boolean, failed: boolean): string {
  if (pinned) return 'Location selected from suggestions.'
  if (fetching) return 'Searching…'
  if (failed) return 'Suggestions unavailable; the typed text will be geocoded.'
  return 'Type 3+ characters for suggestions, or enter any address.'
}
