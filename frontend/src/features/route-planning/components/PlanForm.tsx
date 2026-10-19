import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, type FieldPath, useForm } from 'react-hook-form'
import { Field } from '@/components/forms/Field'
import formStyles from '@/components/forms/forms.module.css'
import { SegmentedControl } from '@/components/forms/SegmentedControl'
import { ApiError, isAbortError } from '@/lib/api-client'
import { browserTimeZone } from '@/lib/date-time'
import type { RoutePlanRequest } from '../api/schemas'
import {
  MAX_LOAD_WEIGHT_LB,
  type PlanFormValues,
  planFormSchema,
  SAMPLING_INTERVALS,
  SERVER_FIELD_PATHS,
  toPlanRequest,
} from '../schemas/plan-form'
import { LocationField } from './LocationField'
import styles from './PlanForm.module.css'

interface PlanFormProps {
  defaultValues: PlanFormValues
  isPending: boolean
  onSubmit: (request: RoutePlanRequest) => Promise<unknown>
  onCancel: () => void
}

const INTERVAL_OPTIONS = SAMPLING_INTERVALS.map((value) => ({ value, label: `${value} mi` }))

export function PlanForm({ defaultValues, isPending, onSubmit, onCancel }: PlanFormProps) {
  const {
    control,
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<PlanFormValues>({
    resolver: zodResolver(planFormSchema),
    defaultValues,
    mode: 'onTouched',
  })

  const submit = handleSubmit(async (values) => {
    try {
      await onSubmit(toPlanRequest(values))
    } catch (error) {
      if (isAbortError(error)) return
      applyServerError(error, setError)
    }
  })

  return (
    <form className={styles.form} onSubmit={(event) => void submit(event)} noValidate>
      <div className={styles.header}>
        <h2 className="eyebrow">Trip</h2>
      </div>

      <Controller
        control={control}
        name="origin"
        render={({ field }) => (
          <LocationField
            id="origin"
            label="Origin"
            placeholder="City, address or facility"
            value={field.value}
            onChange={field.onChange}
            onBlur={field.onBlur}
            error={errors.origin?.query?.message}
          />
        )}
      />
      <Controller
        control={control}
        name="destination"
        render={({ field }) => (
          <LocationField
            id="destination"
            label="Destination"
            placeholder="City, address or facility"
            value={field.value}
            onChange={field.onChange}
            onBlur={field.onBlur}
            error={errors.destination?.query?.message}
          />
        )}
      />

      <div className={styles.row}>
        <Field
          id="departure"
          label="Departure"
          hint={`Local time (${browserTimeZone()})`}
          error={errors.departure?.message}
        >
          {(describedBy) => (
            <input
              id="departure"
              type="datetime-local"
              className={formStyles.input}
              aria-invalid={errors.departure ? true : undefined}
              aria-describedby={describedBy}
              {...register('departure')}
            />
          )}
        </Field>
        <Field
          id="loadWeight"
          label="Load weight (lb)"
          hint={`Cargo only, up to ${MAX_LOAD_WEIGHT_LB.toLocaleString()}`}
          error={errors.loadWeight?.message}
        >
          {(describedBy) => (
            <input
              id="loadWeight"
              type="number"
              inputMode="numeric"
              min={1}
              max={MAX_LOAD_WEIGHT_LB}
              step={1}
              className={`${formStyles.input} numeric`}
              aria-invalid={errors.loadWeight ? true : undefined}
              aria-describedby={describedBy}
              {...register('loadWeight', { valueAsNumber: true })}
            />
          )}
        </Field>
      </div>

      <Controller
        control={control}
        name="interval"
        render={({ field }) => (
          <SegmentedControl
            name="interval"
            legend="Weather checkpoint every"
            options={INTERVAL_OPTIONS}
            value={field.value}
            onChange={field.onChange}
            hint="Measured along each route, plus origin and destination."
          />
        )}
      />

      {errors.root?.server && (
        <p className={styles.formError} role="alert">
          {errors.root.server.message}
        </p>
      )}

      <div className={styles.actions}>
        <button type="submit" className={styles.primary} disabled={isPending}>
          {isPending ? 'Planning routes…' : 'Compare routes'}
        </button>
        {isPending && (
          <button type="button" className={styles.secondary} onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
      {isPending && (
        <p className={styles.progress} role="status">
          Requesting truck routes, then forecasts for every checkpoint. This usually takes 5–20
          seconds.
        </p>
      )}
    </form>
  )
}

type SetError = (name: FieldPath<PlanFormValues> | 'root.server', error: { message: string }) => void

function applyServerError(error: unknown, setError: SetError) {
  if (!(error instanceof ApiError)) {
    setError('root.server', { message: 'Something went wrong. Please try again.' })
    return
  }
  const fieldErrors = error.fieldErrors()
  let mapped = false
  for (const [field, messages] of Object.entries(fieldErrors)) {
    const path = SERVER_FIELD_PATHS[field]
    if (path && messages[0]) {
      setError(path, { message: messages[0] })
      mapped = true
    }
  }
  if (!mapped || error.code !== 'validation_error') {
    setError('root.server', { message: serverMessage(error) })
  }
}

function serverMessage(error: ApiError): string {
  if (error.code === 'rate_limited' && error.retryAfterSeconds !== undefined) {
    return `${error.message} Try again in ${Math.ceil(error.retryAfterSeconds / 60)} min.`
  }
  return error.message
}
