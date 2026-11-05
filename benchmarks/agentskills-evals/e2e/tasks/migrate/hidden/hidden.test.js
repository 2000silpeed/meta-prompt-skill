const request = require('supertest');
const appMod = require('../src/app');
const storeMod = require('../src/store');
const app = appMod.default || appMod.app || appMod;
const store = storeMod.default || storeMod;

beforeEach(() => store.reset());
const items = [{ sku: 'A', qty: 2, price: 10000 }, { sku: 'B', qty: 1, price: 5000 }];

test('H1 list filter by status', async () => {
  await request(app).post('/orders').send({ items });
  await request(app).post('/orders').send({ items });
  await request(app).post('/orders/2/ship');
  const r = await request(app).get('/orders?status=shipped');
  expect(r.body.map(o => o.id)).toEqual(['2']);
});
test('H2 shipped cannot be cancelled', async () => {
  await request(app).post('/orders').send({ items });
  await request(app).post('/orders/1/ship');
  const r = await request(app).post('/orders/1/cancel');
  expect(r.status).toBe(409);
  expect(r.body).toEqual({ error: 'shipped order cannot be cancelled' });
});
test('H3 VIP20 rounding', async () => {
  const r = await request(app).post('/orders').send({ items: [{ sku: 'A', qty: 3, price: 3333 }], coupon: 'VIP20' });
  expect(r.body).toMatchObject({ subtotal: 9999, discount: 2000, shipping: 3000, total: 10999 });
});
test('H4 empty items', async () => {
  const r = await request(app).post('/orders').send({ items: [] });
  expect(r.status).toBe(400);
  expect(r.body).toEqual({ error: 'items must be a non-empty array' });
});
test('H5 missing body', async () => {
  const r = await request(app).post('/orders');
  expect(r.status).toBe(400);
});
test('H6 negative price', async () => {
  const r = await request(app).post('/orders').send({ items: [{ sku: 'A', qty: 1, price: -1 }] });
  expect(r.body.error).toBe('price must be a non-negative number');
});
test('H7 coupon null stored', async () => {
  const r = await request(app).post('/orders').send({ items });
  expect(r.body.coupon).toBeNull();
});
test('H8 free shipping threshold exact', async () => {
  const r = await request(app).post('/orders').send({ items: [{ sku: 'A', qty: 3, price: 10000 }] });
  expect(r.body.shipping).toBe(0);
});
test('H9 404 message', async () => {
  const r = await request(app).post('/orders/42/ship');
  expect(r.body).toEqual({ error: 'order not found' });
});
test('H10 ship twice', async () => {
  await request(app).post('/orders').send({ items });
  await request(app).post('/orders/1/ship');
  const r = await request(app).post('/orders/1/ship');
  expect(r.body.error).toBe('cannot ship shipped order');
});
