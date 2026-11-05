const express = require('express');
const store = require('../store');
const { validateItems } = require('../validate');
const { quote } = require('../services/pricing');

const router = express.Router();

router.post('/', (req, res, next) => {
  const { items, coupon } = req.body || {};
  const msg = validateItems(items);
  if (msg) return res.status(400).json({ error: msg });
  try {
    const q = quote(items, coupon);
    const order = store.create({ items, coupon: coupon || null, ...q });
    res.status(201).json(order);
  } catch (e) { next(e); }
});

router.get('/', (req, res) => {
  const { status } = req.query;
  const all = store.list();
  res.json(status ? all.filter(o => o.status === status) : all);
});

router.get('/:id', (req, res) => {
  const o = store.get(req.params.id);
  if (!o) return res.status(404).json({ error: 'order not found' });
  res.json(o);
});

router.post('/:id/cancel', (req, res) => {
  const o = store.get(req.params.id);
  if (!o) return res.status(404).json({ error: 'order not found' });
  if (o.status === 'shipped') return res.status(409).json({ error: 'shipped order cannot be cancelled' });
  res.json(store.update(o.id, { status: 'cancelled' }));
});

router.post('/:id/ship', (req, res) => {
  const o = store.get(req.params.id);
  if (!o) return res.status(404).json({ error: 'order not found' });
  if (o.status !== 'pending') return res.status(409).json({ error: `cannot ship ${o.status} order` });
  res.json(store.update(o.id, { status: 'shipped' }));
});

module.exports = router;
