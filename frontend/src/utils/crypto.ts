/**
 * 密码加密工具
 * 前端对密码进行 SHA256 哈希后再传输，确保传输安全
 */

// 前端盐值（与后端约定）
const FRONTEND_SALT = 'token_manager_frontend_salt';

/**
 * 对密码进行 SHA256 哈希
 * @param password 原始密码
 * @returns 哈希后的密码
 */
export async function hashPassword(password: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(FRONTEND_SALT + password);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return hashHex;
}
