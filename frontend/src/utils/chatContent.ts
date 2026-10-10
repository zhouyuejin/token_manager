export type ChatContent = string | (
  | { type: 'text'; text: string }
  | { type: 'image_url'; image_url: { url: string } }
)[]

export async function buildChatContent(text: string, files: File[] = []): Promise<ChatContent> {
  if (!files.length) return text
  const images = await Promise.all(files.map(file => new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(new Error('图片读取失败，请重新选择图片'))
    reader.readAsDataURL(file)
  })))
  return [
    ...(text ? [{ type: 'text' as const, text }] : []),
    ...images.map(url => ({ type: 'image_url' as const, image_url: { url } })),
  ]
}
