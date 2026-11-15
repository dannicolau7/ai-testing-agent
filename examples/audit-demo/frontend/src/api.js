const API = process.env.API_BASE;

// The backend reads `sort` but has no `page` parameter.
export const listOrders = () => fetch(`${API}/api/orders?sort=total&page=2`);
export const getOrder = (id) => fetch(`${API}/api/orders/${id}`);
export const createOrder = (body) =>
  fetch("/api/orders", { method: "POST", body: JSON.stringify(body) });
// Leaves out `coupon`, which the backend requires, and sends `giftWrap`, which it ignores.
export const quickOrder = (total) =>
  fetch("/api/orders", { method: "POST", body: JSON.stringify({ total, giftWrap: true }) });
export const deleteOrder = (id) => fetch(`/api/orders/${id}`, { method: "DELETE" });

// The backend has no route for this.
export const refundOrder = (id) => axios.post(`/api/orders/${id}/refund`);

// The backend only defines GET and DELETE on this path.
export const renameOrder = (id, name) =>
  fetch(`/api/orders/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });

// Built at run time: the audit cannot read it.
export const custom = (url) => fetch(url);
