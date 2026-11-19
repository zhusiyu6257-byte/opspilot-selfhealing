export const STATIC_READONLY = import.meta.env.VITE_STATIC_READONLY === '1'
export const READONLY_LIVE = import.meta.env.VITE_READONLY_LIVE === '1'
export const READONLY_API_BASE =
  import.meta.env.VITE_READONLY_API_BASE || '/api/v1'

export const RUNTIME_MODE = STATIC_READONLY
  ? 'static-readonly'
  : READONLY_LIVE
    ? 'readonly-live'
    : 'local-full'
