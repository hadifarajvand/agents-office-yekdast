/**
 * Server-Sent Events (SSE) client for real-time task updates
 *
 * Subscribes to backend events and notifies listeners.
 * Auto-reconnects on failure with exponential backoff.
 */

const SSE_CONFIG = {
  MAX_RETRIES: 5,
  INITIAL_DELAY: 1000,   // 1 second
  MAX_DELAY: 30000,       // 30 seconds
  TIMEOUT: 300000,        // 5 minutes
};

export class SSEClient {
  constructor(apiUrl, onEvent, onError) {
    this.apiUrl = apiUrl;
    this.onEvent = onEvent;
    this.onError = onError;

    this.eventSource = null;
    this.retries = 0;
    this.retryDelay = SSE_CONFIG.INITIAL_DELAY;
    this.isConnected = false;
    this.lastEventTime = null;
  }

  connect() {
    console.log('[SSE] Connecting to event stream...');

    try {
      this.eventSource = new EventSource(`${this.apiUrl}/events`);

      // Handle incoming messages
      this.eventSource.onmessage = (event) => {
        try {
          const { type, data, timestamp } = JSON.parse(event.data);
          this.retries = 0;
          this.retryDelay = SSE_CONFIG.INITIAL_DELAY;
          this.lastEventTime = new Date();

          if (type !== 'ping') {
            console.log(`[SSE] Received ${type}:`, data);
            if (this.onEvent) this.onEvent(type, data);
          }
        } catch (e) {
          console.error('[SSE] Failed to parse event:', e);
        }
      };

      this.eventSource.onerror = () => {
        this.isConnected = false;
        console.warn('[SSE] Connection lost');
        this.eventSource.close();

        if (this.retries < SSE_CONFIG.MAX_RETRIES) {
          this.retries++;
          const nextDelay = Math.min(
            this.retryDelay * Math.pow(2, this.retries - 1),
            SSE_CONFIG.MAX_DELAY
          );
          console.log(`[SSE] Retrying in ${nextDelay}ms (attempt ${this.retries}/${SSE_CONFIG.MAX_RETRIES})`);

          setTimeout(() => this.connect(), nextDelay);
        } else {
          console.error('[SSE] Max retries reached, falling back to polling');
          if (this.onError) this.onError('max_retries_exceeded');
        }
      };

      this.isConnected = true;
      console.log('[SSE] Connected successfully');
    } catch (e) {
      console.error('[SSE] Failed to connect:', e);
      if (this.onError) this.onError('connection_failed');
    }
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.isConnected = false;
      console.log('[SSE] Disconnected');
    }
  }

  getStatus() {
    return {
      isConnected: this.isConnected,
      retries: this.retries,
      lastEventTime: this.lastEventTime,
    };
  }
}

// Global SSE instance
let sseClient = null;

export function initSSE(apiUrl, onEvent, onError) {
  if (sseClient) {
    sseClient.disconnect();
  }

  sseClient = new SSEClient(apiUrl, onEvent, onError);
  sseClient.connect();

  return sseClient;
}

export function disconnectSSE() {
  if (sseClient) {
    sseClient.disconnect();
    sseClient = null;
  }
}

export function getSSEStatus() {
  return sseClient ? sseClient.getStatus() : null;
}
