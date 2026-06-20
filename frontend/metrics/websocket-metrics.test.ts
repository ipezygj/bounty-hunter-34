import { ReconnectMetrics } from './websocket-metrics';

describe('ReconnectMetrics', () => {
  let metrics: ReconnectMetrics;

  beforeEach(() => {
    metrics = new ReconnectMetrics();
  });

  test('initial state has zero attempts', () => {
    expect(metrics.getMetrics().reconnectAttemptCount).toBe(0);
  });

  test('recordReconnectAttempt increments count', () => {
    metrics.recordReconnectAttempt();
    metrics.recordReconnectAttempt();
    expect(metrics.getMetrics().reconnectAttemptCount).toBe(2);
  });

  test('recordDisconnect stores reason', () => {
    metrics.recordDisconnect('timeout');
    expect(metrics.getMetrics().lastDisconnectReason).toBe('timeout');
  });

  test('recordConnected updates timestamp', () => {
    const before = Date.now();
    metrics.recordConnected();
    const after = Date.now();
    const ts = metrics.getMetrics().lastConnectedTimestamp;
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });
});
