/**
 * ERP Service — Production-Grade Entry Point
 * AI Trading Command Center
 * ─────────────────────────────────────────────────────────
 * Phase 1  Security Hardening  (API Key Auth, HMAC Signatures)
 * Phase 2  Idempotency         (Webhook deduplication)
 * Phase 3  Trade Audit Trail   (trade_positions table)
 * Phase 4  DB Performance      (indexes, connection pool tuning)
 * Phase 5  Analytics           (/api/open-positions, /api/trades, /api/performance)
 * Phase 6  Accounting          (partial close, break-even, trailing stop events)
 * Phase 7  Observability       (/health/deep, /metrics)
 * Phase 8  Production Rules    (no hardcoded secrets, parameterized queries)
 */

import express from 'express';
import cors from 'cors';

import { pool, initDb, checkDbHealth, getPendingDeliveries } from './db/database.mjs';
import {
  apiKeyAuth,
  validateWebhookSignature,
  correlationId,
  setAuditPool,
  logAudit
} from './middleware/apiKeyAuth.mjs';
import {
  handleTradeEvent,
  getLedger,
  getTaxSummary,
  getSummary,
  getOpenPositions,
  getTrades,
  getPerformance,
  getMetrics,
  resetERP
} from './routes/handlers.mjs';

const app = express();
const PORT = parseInt(process.env.PORT || '5001', 10);

// ─────────────────────────────────────────────────────────
// Global Middleware
// ─────────────────────────────────────────────────────────

app.use(cors({
  origin: '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Api-Key', 'Idempotency-Key', 'X-Idempotency-Key', 'X-Signature', 'X-Correlation-Id'],
  exposedHeaders: ['X-Correlation-Id']
}));

// Capture raw body inside JSON parsing to prevent double-reading the stream
app.use(express.json({
  verify: (req, res, buf, encoding) => {
    req.rawBody = buf.toString(encoding || 'utf8');
  }
}));


// Correlation ID injection (all requests)
app.use(correlationId);

// Connect audit pool for in-request log writes
setAuditPool(pool);

// API Key auth (protects everything except /health*)
app.use(apiKeyAuth);

// Request logger
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    console.log(`[ERP][${req.correlationId}] ${req.method} ${req.path} → ${res.statusCode} (${Date.now() - start}ms)`);
  });
  next();
});

// ─────────────────────────────────────────────────────────
// Health Routes (Public — no auth)
// ─────────────────────────────────────────────────────────

app.get('/health', async (req, res) => {
  try {
    const countRes = await pool.query('SELECT count(*) as c FROM erp_ledger');
    const statsRes = await pool.query('SELECT accumulated_pnl FROM erp_stats WHERE id = 1');
    return res.json({
      status: 'ok',
      uptime: process.uptime(),
      ledgerEntries: parseInt(countRes.rows[0].c),
      totalPnL: statsRes.rows[0]?.accumulated_pnl ?? 0,
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    return res.status(500).json({ status: 'error', error: err.message });
  }
});

app.get('/health/deep', async (req, res) => {
  const dbOk = await checkDbHealth();
  const failedDeliveries = await getPendingDeliveries();
  const status = dbOk ? 'ok' : 'degraded';

  return res.status(dbOk ? 200 : 503).json({
    status,
    checks: {
      database: dbOk ? 'ok' : 'error',
      pendingDeliveries: failedDeliveries,
      nodeVersion: process.version,
      memoryMB: Number((process.memoryUsage().rss / 1024 / 1024).toFixed(1))
    },
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

// ─────────────────────────────────────────────────────────
// Webhook — HMAC signature verified, idempotent
// ─────────────────────────────────────────────────────────

app.post('/webhook/trade-event', validateWebhookSignature, handleTradeEvent);

// ─────────────────────────────────────────────────────────
// ERP API Routes (all protected by apiKeyAuth)
// ─────────────────────────────────────────────────────────

// Ledger
app.get('/api/ledger', getLedger);
app.get('/api/erp/ledger', getLedger);          // Legacy compat

// Tax & Accounting
app.get('/api/tax-summary', getTaxSummary);
app.get('/api/erp/tax-summary', getTaxSummary);  // Legacy compat
app.get('/api/summary', getSummary);
app.get('/api/erp/summary', getSummary);         // Legacy compat

// Position Tracking (Phase 5)
app.get('/api/open-positions', getOpenPositions);
app.get('/api/trades', getTrades);
app.get('/api/performance', getPerformance);

// Observability (Phase 7)
app.get('/metrics', getMetrics);

// Restricted admin route (development only — Phase 1)
app.delete('/api/reset', resetERP);

// ─────────────────────────────────────────────────────────
// 404 Catch-all
// ─────────────────────────────────────────────────────────

app.use((req, res) => {
  res.status(404).json({ success: false, error: `Route not found: ${req.method} ${req.path}` });
});

// ─────────────────────────────────────────────────────────
// Global Error Handler
// ─────────────────────────────────────────────────────────

app.use((err, req, res, next) => {
  console.error('[ERP][UnhandledError]', err);
  res.status(500).json({ success: false, error: 'Internal server error.' });
});

// ─────────────────────────────────────────────────────────
// Startup
// ─────────────────────────────────────────────────────────

await initDb();

const server = app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 [ERP Server v2] รันบนพอร์ต http://localhost:${PORT}`);
  console.log(`🔐 [ERP] Security: API Key Auth + HMAC Webhook Signatures ACTIVE`);
  console.log(`🗄️  [ERP] Database: PostgreSQL connected (pool max=${parseInt(process.env.DB_POOL_MAX || '20')})`);
  console.log(`📊 [ERP] Routes: /webhook/trade-event, /api/ledger, /api/trades, /api/performance, /health/deep, /metrics`);
  console.log(`🌍 [ERP] Environment: ${process.env.NODE_ENV || 'development'}`);
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`\n❌ [ERP] พอร์ต ${PORT} ถูกใช้งานอยู่แล้ว!`);
    console.error(`   วิธีแก้: lsof -ti :${PORT} | xargs kill -9\n`);
    process.exit(1);
  } else {
    console.error('[ERP] Server error:', err);
    process.exit(1);
  }
});

// Graceful shutdown
const shutdown = async (signal) => {
  console.log(`\n[ERP] Received ${signal}. Shutting down gracefully...`);
  server.close(async () => {
    await pool.end();
    console.log('[ERP] Database pool closed. Goodbye.');
    process.exit(0);
  });
  setTimeout(() => {
    console.error('[ERP] Forced shutdown after timeout.');
    process.exit(1);
  }, 10000);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
