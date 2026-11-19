import http from 'node:http'

const upstreamBase = process.env.READONLY_UPSTREAM || 'http://127.0.0.1:8000'
const port = Number(process.env.READONLY_PROXY_PORT || 8081)
const allowedOrigins = (
  process.env.READONLY_ALLOWED_ORIGINS ||
  'https://opspilot.de5.net,http://127.0.0.1:5177,http://localhost:5177'
)
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean)

const allowedPaths = new Set([
  '/api/v1/healthz',
  '/api/v1/assets',
  '/api/v1/executions',
  '/api/v1/executions/stats',
])

function isAllowedPath(pathname) {
  if (allowedPaths.has(pathname)) return true
  return /^\/api\/v1\/executions\/by-task\/[^/]+$/.test(pathname)
}

function resolveOrigin(req) {
  const origin = req.headers.origin
  if (!origin) return allowedOrigins[0]
  return allowedOrigins.includes(origin) ? origin : null
}

function corsHeaders(origin) {
  if (!origin) return {}
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Accept, Content-Type',
    Vary: 'Origin',
  }
}

function sendJson(res, status, payload, origin, extra = {}) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    ...corsHeaders(origin),
    ...extra,
  })
  res.end(JSON.stringify(payload))
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', upstreamBase)
  const origin = resolveOrigin(req)

  if (req.headers.origin && !origin) {
    sendJson(res, 403, { detail: 'origin is not allowed' }, null)
    return
  }

  if (req.method === 'OPTIONS') {
    if (!origin) {
      sendJson(res, 403, { detail: 'origin is not allowed' }, null)
      return
    }
    res.writeHead(204, corsHeaders(origin))
    res.end()
    return
  }

  if (req.method !== 'GET') {
    sendJson(res, 405, { detail: 'readonly proxy allows GET only' }, origin)
    return
  }

  if (!isAllowedPath(url.pathname)) {
    sendJson(res, 403, { detail: 'path is not allowed by readonly proxy' }, origin)
    return
  }

  try {
    const upstream = await fetch(`${upstreamBase}${url.pathname}${url.search}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })
    const body = await upstream.text()
    res.writeHead(upstream.status, {
      'Content-Type': upstream.headers.get('content-type') || 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...corsHeaders(origin),
    })
    res.end(body)
  } catch (error) {
    sendJson(
      res,
      502,
      {
        detail: 'upstream unavailable',
        error: error instanceof Error ? error.message : String(error),
      },
      origin,
    )
  }
})

server.listen(port, '127.0.0.1', () => {
  console.log(`readonly proxy listening on http://127.0.0.1:${port}`)
  console.log(`upstream: ${upstreamBase}`)
  console.log(`allowed origins: ${allowedOrigins.join(', ')}`)
})
