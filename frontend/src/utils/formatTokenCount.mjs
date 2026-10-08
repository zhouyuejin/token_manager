export const formatTokenCount = (value) => {
  if (value >= 100000000) return `${parseFloat((value / 100000000).toFixed(2))} 亿`
  if (value >= 10000) return `${parseFloat((value / 10000).toFixed(1))} 万`
  return value.toLocaleString()
}
