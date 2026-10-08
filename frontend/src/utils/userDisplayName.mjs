export const userDisplayName = (user) => user?.nickname?.trim() || user?.username || user?.user_id || ''
