// Every call the page makes to its own backend carries two headers the server insists on:
//   X-AO-Client: office   a custom header a cross-site form or simple fetch cannot send, which
//                         is what keeps another web page from driving the office
//   X-AO-Token: <token>   only when the server was started with AO_API_TOKEN; the server puts it
//                         in a <meta name="ao-token"> tag of the page it serves
// Installed once, here, so no call site has to remember them.
const meta = typeof document !== 'undefined' && document.querySelector('meta[name="ao-token"]');
const token = meta ? meta.content : '';
const nativeFetch = typeof window !== 'undefined' && window.fetch ? window.fetch.bind(window) : null;

export function installApiHeaders() {
  if (!nativeFetch || window.__aoFetch) return;
  window.__aoFetch = true;
  window.fetch = (input, init = {}) => {
    const url = typeof input === 'string' ? input : input && input.url;
    if (typeof url === 'string' && (url.startsWith('/api/') || url.startsWith(location.origin + '/api/'))) {
      const headers = new Headers(init.headers || (typeof input !== 'string' ? input.headers : undefined) || {});
      headers.set('X-AO-Client', 'office');
      if (token) headers.set('X-AO-Token', token);
      init = { ...init, headers };
    }
    return nativeFetch(input, init);
  };
}
installApiHeaders();
