import { getTaskStatus } from '../api'

/** Celery 终态：到达这些状态后停止轮询 */
export const TERMINAL_STATES = ['SUCCESS', 'FAILURE', 'REVOKED']

export class TaskPollingError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'TaskPollingError'
    this.code = code
  }
}

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new TaskPollingError('ABORTED', '轮询已取消'))
      return
    }

    const cleanup = () => signal?.removeEventListener('abort', onAbort)
    const onAbort = () => {
      clearTimeout(timer)
      cleanup()
      reject(new TaskPollingError('ABORTED', '轮询已取消'))
    }
    const timer = setTimeout(() => {
      cleanup()
      resolve()
    }, ms)

    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

/**
 * 通用短轮询：下发任务拿到 task_id 后调用，直到终态 / 超时 / 取消。
 * - 用 setTimeout 串行等待，不会像 setInterval 那样堆叠并发请求
 * - 单次查询失败可容忍 2 次抖动，第 3 次才判定为网络故障
 * - onUpdate 每次都拿到 { status, result, attempts, elapsedMs }，供 UI 打点日志
 */
export async function pollTask(taskId, options = {}) {
  const {
    interval = 1200,
    timeoutMs = 90000,
    maxAttempts = 90,
    signal,
    onUpdate,
  } = options

  const startedAt = Date.now()
  let attempts = 0
  let consecutiveErrors = 0

  const emit = (payload) =>
    onUpdate?.({
      ...payload,
      attempts,
      elapsedMs: Date.now() - startedAt,
    })

  while (true) {
    if (signal?.aborted) throw new TaskPollingError('ABORTED', '轮询已取消')
    if (attempts >= maxAttempts) {
      throw new TaskPollingError('TIMEOUT', `已轮询 ${attempts} 次，任务仍未结束`)
    }
    if (Date.now() - startedAt >= timeoutMs) {
      throw new TaskPollingError(
        'TIMEOUT',
        `任务等待超时（${Math.round(timeoutMs / 1000)} 秒），已停止前端轮询`,
      )
    }

    attempts += 1
    let snapshot
    try {
      snapshot = await getTaskStatus(taskId, { signal })
      consecutiveErrors = 0
    } catch (err) {
      if (signal?.aborted || err?.code === 'ERR_CANCELED') {
        throw new TaskPollingError('ABORTED', '轮询已取消')
      }
      consecutiveErrors += 1
      emit({
        status: 'RETRYING',
        message: `状态查询失败：${err.message}（第 ${consecutiveErrors} 次）`,
      })
      if (consecutiveErrors >= 3) {
        throw new TaskPollingError(
          'NETWORK',
          `连续 ${consecutiveErrors} 次无法查询任务状态：${err.message}`,
        )
      }
      await sleep(interval, signal)
      continue
    }

    emit({
      status: snapshot?.status || 'PENDING',
      result: snapshot?.result ?? null,
      taskId: snapshot?.task_id || taskId,
    })

    if (TERMINAL_STATES.includes(snapshot?.status)) return snapshot
    await sleep(interval, signal)
  }
}
