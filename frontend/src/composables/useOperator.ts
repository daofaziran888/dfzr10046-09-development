import { ref } from 'vue'

/**
 * 当前操作员是跨页面共享的单例状态，并持久化到 localStorage：
 * 刷新后仍保留“我是谁”，制单人/签核人/发布人输入框据此预填。
 */
const STORAGE_KEY = 'vl_current_operator'
const FALLBACK_KEYS = ['operator', 'current_operator', 'currentOperator', 'x-operator']

function readStored(): string {
  try {
    const params = new URLSearchParams(window.location.search)
    const fromQuery = params.get('operator') || params.get('as') || params.get('user')
    if (fromQuery && fromQuery.trim()) return fromQuery.trim()
    const mine = window.localStorage.getItem(STORAGE_KEY)
    if (mine && mine.trim()) return mine
    for (const key of FALLBACK_KEYS) {
      const value = window.localStorage.getItem(key)
      if (value && value.trim()) return value.trim()
    }
  } catch {
    /* 忽略存储/URL 读取失败 */
  }
  return ''
}

const currentOperator = ref<string>(readStored() || '张三')

export function useOperator() {
  function setOperator(name: string) {
    currentOperator.value = name
    try {
      window.localStorage.setItem(STORAGE_KEY, name)
    } catch {
      /* 隐私模式等场景下忽略持久化失败 */
    }
  }

  return { currentOperator, setOperator }
}

export function operatorName(): string {
  return currentOperator.value.trim()
}

/**
 * 给写请求附带操作人头。HTTP 头只能是 ISO-8859-1，中文姓名不能放进头里，
 * 因此非 Latin-1 标识（如中文姓名）返回空头，操作人改由 JSON body 传递。
 */
export function operatorHeaders(): Record<string, string> {
  const name = operatorName()
  if (!name) return {}
  // eslint-disable-next-line no-control-regex
  if (/^[\u0000-ÿ]*$/.test(name)) return { 'X-Operator': name }
  return {}
}
