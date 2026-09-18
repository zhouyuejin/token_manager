// Strip <think>...</think> blocks from model output.
//
// Reason: reasoning-capable models (MiniMax-M3, DeepSeek-R1, etc.)
// inline their chain-of-thought inside the assistant `content` field,
// wrapped in <think>...</think>. Without this filter those blocks leak
// into the chat UI as literal text.
//
// Use this on the presentation boundary (display + streaming accumulator),
// not on stored data: backend should still record what the model actually
// returned so future debugging has the full signal.

// Hide unfinished blocks too: the closing tag may arrive in a later chunk.
const THINK_TAG_RE = /<think>[\s\S]*?(?:<\/think>|$)/g
const PARTIAL_THINK_TAG_RE = /<(?:t|th|thi|thin|think)?$/

export const stripThinkTags = (content: string): string =>
  (content ?? '').replace(THINK_TAG_RE, '').replace(PARTIAL_THINK_TAG_RE, '')
