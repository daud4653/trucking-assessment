import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})

if (!('randomUUID' in crypto)) {
  Object.defineProperty(crypto, 'randomUUID', { value: () => '00000000-0000-4000-8000-000000000000' })
}

// jsdom does not implement modal dialogs.
Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
  configurable: true,
  value: function showModal(this: HTMLDialogElement) {
    this.setAttribute('open', '')
  },
})
