const express = require('express');
const orders = require('./routes/orders');

const app = express();
app.use(express.json());
app.get('/health', (req, res) => res.json({ ok: true }));
app.use('/orders', orders);
app.use((err, req, res, next) => {
  res.status(err.status || 500).json({ error: err.message || 'internal error' });
});

module.exports = app;
