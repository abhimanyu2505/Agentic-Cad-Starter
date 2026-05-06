const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json();
}

export function getState() {
  return request("/state");
}

export function generate(prompt) {
  return request("/generate", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export function modify({ componentId, parameters, prompt }) {
  return request("/modify", {
    method: "POST",
    body: JSON.stringify({
      component_id: componentId || null,
      parameters: parameters || null,
      prompt: prompt || null,
    }),
  });
}

export { API_BASE };
