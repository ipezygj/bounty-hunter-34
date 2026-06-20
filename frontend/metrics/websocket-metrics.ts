/**
 * WebSocket Reconnect Metrics Tracker (#73)
 * Tracks reconnection attempts, disconnection reasons, and connection timestamps
 */

export interface WebSocketMetrics {
  reconnectAttemptCount: number;
  lastDisconnectReason?: string;
  lastConnectedTimestamp?: number;
}

export class ReconnectMetrics {
  private metrics: WebSocketMetrics = {
    reconnectAttemptCount: 0,
  };

  recordReconnectAttempt(): void {
    this.metrics.reconnectAttemptCount++;
  }

  recordDisconnect(reason: string): void {
    this.metrics.lastDisconnectReason = reason;
  }

  recordConnected(): void {
    this.metrics.lastConnectedTimestamp = Date.now();
  }

  getMetrics(): WebSocketMetrics {
    return { ...this.metrics };
  }
}
