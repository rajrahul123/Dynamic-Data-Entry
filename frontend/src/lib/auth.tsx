import { useEffect, useState, type ReactNode } from 'react'

import {
  ApiError,
  fetchMe,
  getToken,
  login as apiLogin,
  setToken,
  type User,
} from './api'
import { AuthContext, type AuthContextValue } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [initializing, setInitializing] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function restoreSession() {
      if (!getToken()) {
        if (!cancelled) setInitializing(false)
        return
      }
      try {
        const me = await fetchMe()
        if (!cancelled) setUser(me)
      } catch (error) {
        if (error instanceof ApiError) setToken(null)
      } finally {
        if (!cancelled) setInitializing(false)
      }
    }

    function onUnauthorized() {
      setUser(null)
    }

    void restoreSession()
    window.addEventListener('auth:unauthorized', onUnauthorized)

    return () => {
      cancelled = true
      window.removeEventListener('auth:unauthorized', onUnauthorized)
    }
  }, [])

  async function login(username: string, password: string) {
    const { access_token } = await apiLogin(username, password)
    setToken(access_token)
    const me = await fetchMe()
    setUser(me)
  }

  function logout() {
    setToken(null)
    setUser(null)
  }

  const value: AuthContextValue = { user, initializing, login, logout }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}