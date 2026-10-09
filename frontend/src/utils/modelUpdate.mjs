export function modelUpdate(values, model) {
  const update = { ...values }
  for (const field of ['price_per_1k_input', 'price_per_1k_output', 'price_per_request']) {
    if (update[field] != null && Number(update[field]) === Number(model[field] || 0)) delete update[field]
  }
  return update
}
