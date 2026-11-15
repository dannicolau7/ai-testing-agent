const API = process.env.API_BASE;

export const listOrders = () => fetch(`${API}/api/orders`);
export const getOrder = (id) => fetch(`${API}/api/orders/${id}`);
export const createOrder = (body) =>
  fetch("/api/orders", { method: "POST", body: JSON.stringify(body) });
export const deleteOrder = (id) => fetch(`/api/orders/${id}`, { method: "DELETE" });

// The backend has no route for this.
export const refundOrder = (id) => axios.post(`/api/orders/${id}/refund`);

// The backend only defines GET and DELETE on this path.
export const renameOrder = (id, name) =>
  fetch(`/api/orders/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });

// Built at run time: the audit cannot read it.
export const custom = (url) => fetch(url);
