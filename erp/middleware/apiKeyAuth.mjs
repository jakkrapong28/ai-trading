import crypto from 'crypto';

// ─────────────────────────────────────────────────────────
// API Key Authentication Middleware
// Protects all routes except GET /health
// ─────────────────────────────────────────────────────────
export function apiKeyAuth(req, res, next) {
  // Public routes exempt from auth (incl. Prometheus scrape — aggregate counts,
  // no secrets, and scrapers can't send a custom X-Api-Key easily).
  const publicPaths = ['/health', '/health/deep', '/metrics/prometheus'];
  if (publicPaths.includes(req.path) && req.method === 'GET') {
    return next();
  }

  const apiKey = process.env.ERP_API_KEY;
  if (!apiKey) {
    console.error('[ERP][Security] ERP_API_KEY not configured. Denying all protected requests.');
    return res.status(503).json({ success: false, error: 'Service not properly configured.' });
  }

  const provided = req.headers['x-api-key'] || req.headers['authorization']?.replace('Bearer ', '');
  if (!provided || provided !== apiKey) {
    logAudit(req, 'AUTH_FAILED', { reason: 'Invalid or missing API key' });
    return res.status(401).json({ success: false, error: 'Unauthorized. Valid X-Api-Key header required.' });
  }

  next();
}

// ─────────────────────────────────────────────────────────
// Webhook HMAC Signature Validation
// Trading backend sends: x-signature: sha256=<hex>
// ─────────────────────────────────────────────────────────
export function validateWebhookSignature(req, res, next) {
  const secret = process.env.ERP_WEBHOOK_SECRET;
  if (!secret) {
    // If no secret configured, skip validation (development mode)
    return next();
  }

  const signatureHeader = req.headers['x-signature'];
  if (!signatureHeader) {
    logAudit(req, 'WEBHOOK_MISSING_SIG', { path: req.path });
    return res.status(401).json({ success: false, error: 'Missing x-signature header.' });
  }

  const rawBody = req.rawBody || JSON.stringify(req.body);
  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(rawBody, 'utf8')
    .digest('hex');

  const provided = signatureHeader;

  // Constant-time comparison to prevent timing attacks
  let isValid = false;
  try {
    isValid = crypto.timingSafeEqual(
      Buffer.from(expected, 'utf8'),
      Buffer.from(provided.padEnd(expected.length, '0'), 'utf8')
    ) && expected.length === provided.length;
  } catch {
    isValid = false;
  }

  if (!isValid) {
    logAudit(req, 'WEBHOOK_SIG_INVALID', { path: req.path });
    return res.status(401).json({ success: false, error: 'Invalid webhook signature.' });
  }

  next();
}

// ─────────────────────────────────────────────────────────
// Correlation ID Middleware
// Injects x-correlation-id for structured logging
// ─────────────────────────────────────────────────────────
export function correlationId(req, res, next) {
  const id = req.headers['x-correlation-id'] || crypto.randomUUID();
  req.correlationId = id;
  res.setHeader('x-correlation-id', id);
  next();
}

// ─────────────────────────────────────────────────────────
// Audit log helper (in-process; pool injected later)
// ─────────────────────────────────────────────────────────
let _auditPool = null;
export function setAuditPool(pool) { _auditPool = pool; }

export async function logAudit(req, eventType, payload = {}) {
  if (!_auditPool) return;
  try {
    await _auditPool.query(
      `INSERT INTO audit_logs (event_type, user_agent, ip_address, correlation_id, payload, created_at)
       VALUES ($1, $2, $3, $4, $5, NOW())`,
      [
        eventType,
        req?.headers?.['user-agent'] || 'unknown',
        req?.ip || req?.connection?.remoteAddress || 'unknown',
        req?.correlationId || null,
        JSON.stringify(payload)
      ]
    );
  } catch (err) {
    console.error('[ERP][Audit] Failed to write audit log:', err.message);
  }
}
