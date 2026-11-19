export const STATIC_READONLY = import.meta.env.VITE_STATIC_READONLY === '1'

export const RUNTIME_MODE = STATIC_READONLY ? 'static-readonly' : 'local-full'
