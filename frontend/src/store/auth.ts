import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  login as loginApi,
  refresh as refreshApi,
  logoutServer,
  LoginParams,
  getCurrentUser,
  UserInfo,
} from '../api/auth'

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: UserInfo | null
  isLoading: boolean

  login: (params: LoginParams) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>

  // 给 request 拦截器在 refresh 成功后写入新 token
  setAuth: (access: string, refresh: string) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      isLoading: false,

      login: async (params) => {
        set({ isLoading: true })
        try {
          const response = await loginApi(params)

          set({ token: response.access_token, refreshToken: response.refresh_token })

          const userInfo = await getCurrentUser()
          set({ user: userInfo, isLoading: false })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: async () => {
        const rt = get().refreshToken
        // 先清本地 store，避免撤销请求本身 401 时也被踢
        set({ token: null, refreshToken: null, user: null })
        if (rt) {
          try {
            await logoutServer(rt)
          } catch {
            // 即使服务端撤销失败也不影响本地登出
          }
        }
      },

      checkAuth: async () => {
        const token = get().token
        if (!token) return
        try {
          const user = await getCurrentUser()
          set({ user })
        } catch {
          set({ token: null, refreshToken: null, user: null })
        }
      },

      setAuth: (access, refresh) => {
        set({ token: access, refreshToken: refresh })
      },
    }),
    {
      name: 'auth-storage',
      // 同时持久化两个 token，refresh token 用于 access 过期后静默续期
      partialize: (state) => ({ token: state.token, refreshToken: state.refreshToken }),
    }
  )
)
