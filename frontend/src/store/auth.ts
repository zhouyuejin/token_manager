import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { login as loginApi, LoginParams, getCurrentUser, UserInfo } from '../api/auth'

interface AuthState {
  token: string | null
  user: UserInfo | null
  isLoading: boolean
  login: (params: LoginParams) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoading: false,

      login: async (params: LoginParams) => {
        set({ isLoading: true })
        try {
          const formData = new URLSearchParams()
          formData.append('username', params.username)
          formData.append('password', params.password)
          
          const response = await loginApi(formData as any)
          
          // 先存储 token，确保后续请求携带 Authorization header
          set({ token: response.access_token })
          
          // 从 /auth/login 获取的用户信息较少，需要调用 /users/me 获取完整信息
          // 现在 token 已经在 store 中了，request 拦截器可以正确获取
          const userInfo = await getCurrentUser()
          
          set({
            user: userInfo,
            isLoading: false
          })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: () => {
        set({ token: null, user: null })
      },

      checkAuth: async () => {
        const token = get().token
        if (!token) return
        
        try {
          const user = await getCurrentUser()
          set({ user })
        } catch {
          set({ token: null, user: null })
        }
      }
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token })
    }
  )
)
