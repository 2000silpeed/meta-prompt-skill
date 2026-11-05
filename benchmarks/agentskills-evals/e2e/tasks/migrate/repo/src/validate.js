function validateItems(items) {
  if (!Array.isArray(items) || items.length === 0) return 'items must be a non-empty array';
  for (const it of items) {
    if (typeof it.sku !== 'string' || !it.sku) return 'sku is required';
    if (!Number.isInteger(it.qty) || it.qty <= 0) return 'qty must be a positive integer';
    if (typeof it.price !== 'number' || it.price < 0) return 'price must be a non-negative number';
  }
  return null;
}
module.exports = { validateItems };
