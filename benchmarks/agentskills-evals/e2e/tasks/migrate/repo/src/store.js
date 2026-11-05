const orders = new Map();
let seq = 1;

function reset() { orders.clear(); seq = 1; }
function create(data) { const id = String(seq++); const o = { id, status: 'pending', ...data }; orders.set(id, o); return o; }
function get(id) { return orders.get(String(id)) || null; }
function update(id, patch) { const o = get(id); if (!o) return null; Object.assign(o, patch); return o; }
function list() { return Array.from(orders.values()); }

module.exports = { reset, create, get, update, list };
