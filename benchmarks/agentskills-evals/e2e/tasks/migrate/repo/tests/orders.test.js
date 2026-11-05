const request = require('supertest');
const app = require('../src/app');
const store = require('../src/store');

beforeEach(() => store.reset());
const items = [{ sku: 'A', qty: 2, price: 10000 }, { sku: 'B', qty: 1, price: 5000 }];

test('health', async () => {
  const r = await request(app).get('/health');
  expect(r.body).toEqual({ ok: true });
});

test('create order computes totals', async () => {
  const r = await request(app).post('/orders').send({ items });
  expect(r.status).toBe(201);
  expect(r.body).toMatchObject({ id: '1', status: 'pending', subtotal: 25000, discount: 0, shipping: 3000, total: 28000 });
});

test('coupon and free shipping', async () => {
  const r = await request(app).post('/orders').send({ items: [{ sku: 'A', qty: 4, price: 10000 }], coupon: 'WELCOME10' });
  expect(r.body).toMatchObject({ subtotal: 40000, discount: 4000, shipping: 0, total: 36000 });
});

test('unknown coupon is 400', async () => {
  const r = await request(app).post('/orders').send({ items, coupon: 'NOPE' });
  expect(r.status).toBe(400);
  expect(r.body.error).toBe('unknown coupon');
});

test('validation error', async () => {
  const r = await request(app).post('/orders').send({ items: [{ sku: 'A', qty: 0, price: 1 }] });
  expect(r.status).toBe(400);
  expect(r.body.error).toBe('qty must be a positive integer');
});

test('get / 404', async () => {
  const r = await request(app).get('/orders/99');
  expect(r.status).toBe(404);
});

test('cancel then ship conflicts', async () => {
  await request(app).post('/orders').send({ items });
  await request(app).post('/orders/1/cancel');
  const r = await request(app).post('/orders/1/ship');
  expect(r.status).toBe(409);
  expect(r.body.error).toBe('cannot ship cancelled order');
});
