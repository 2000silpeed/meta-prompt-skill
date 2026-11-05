const COUPONS = { WELCOME10: 0.1, VIP20: 0.2 };

function subtotal(items) {
  return items.reduce((s, it) => s + it.price * it.qty, 0);
}

function quote(items, coupon) {
  const sub = subtotal(items);
  const rate = coupon ? COUPONS[coupon] : 0;
  if (coupon && rate === undefined) {
    const err = new Error('unknown coupon');
    err.status = 400;
    throw err;
  }
  const discount = Math.round(sub * rate);
  const shipping = sub - discount >= 30000 ? 0 : 3000;
  return { subtotal: sub, discount, shipping, total: sub - discount + shipping };
}

module.exports = { quote, subtotal, COUPONS };
