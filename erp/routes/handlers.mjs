import { pool } from '../db/database.mjs';
import { logAudit } from '../middleware/apiKeyAuth.mjs';

const VAT_RATE = parseFloat(process.env.VAT_RATE || '0.07');
const CORPORATE_TAX_RATE = parseFloat(process.env.CORPORATE_TAX_RATE || '0.20');

// ─────────────────────────────────────────────────────────
// Idempotency check — returns existing record or null
// ─────────────────────────────────────────────────────────
async function checkIdempotency(client, idempotencyKey) {
  if (!idempotencyKey) return null;
  const res = await client.query(
    `SELECT id, status, response_code FROM erp_delivery_records WHERE idempotency_key = $1`,
    [idempotencyKey]
  );
  return res.rows[0] || null;
}

async function markDelivery(client, idempotencyKey, event, payload, status, responseCode = 200) {
  if (!idempotencyKey) return;
  await client.query(
    `INSERT INTO erp_delivery_records (idempotency_key, event, status, response_code, payload, created_at)
     VALUES ($1, $2, $3, $4, $5, NOW())
     ON CONFLICT (idempotency_key) DO UPDATE SET status = $3, response_code = $4`,
    [idempotencyKey, event, status, responseCode, JSON.stringify(payload)]
  );
}

// ─────────────────────────────────────────────────────────
// POST /webhook/trade-event
// ─────────────────────────────────────────────────────────
export async function handleTradeEvent(req, res) {
  const { event, data } = req.body;
  const idempotencyKey = req.headers['idempotency-key'] || req.headers['x-idempotency-key'];
  const correlationId = req.correlationId;

  console.log(`[ERP][${correlationId}] ← Event: ${event}`, JSON.stringify(data));

  if (!event || !data) {
    return res.status(400).json({ success: false, error: 'Missing event or data fields.' });
  }

  await logAudit(req, 'WEBHOOK_RECEIVED', { event, tradeId: data.trade_id || data.symbol });

  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // ── Idempotency guard ─────────────────────────────────
    if (idempotencyKey) {
      const existing = await checkIdempotency(client, idempotencyKey);
      if (existing) {
        await client.query('ROLLBACK');
        console.log(`[ERP][${correlationId}] Duplicate delivery detected: ${idempotencyKey}`);
        return res.status(200).json({ success: true, duplicate: true, message: 'Duplicate event — already processed.' });
      }
    }

    const timestamp = new Date().toISOString();
    const txId = `tx_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

    switch (event) {

      case 'trade.opened': {
        const amount = Number(((data.price || 0) * (data.volume || data.lot_size || 0.01)).toFixed(2));
        const description = `เปิดออเดอร์ ${data.action} ${data.symbol} @ ${data.price} (Lot: ${data.volume || data.lot_size})`;

        await client.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount, trade_id, correlation_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event, description,
           '10200 - พอร์ตลงทุน (ระหว่างเทรด)', amount,
           '10100 - เงินสดในบัญชีเทรด', amount,
           data.trade_id || txId, correlationId]
        );

        // Insert trade position record
        await client.query(
          `INSERT INTO trade_positions (trade_id, symbol, action, entry_price, lot_size, stop_loss, take_profit, atr_at_entry, opened_at, status)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), 'OPEN')
           ON CONFLICT (trade_id) DO NOTHING`,
          [
            data.trade_id || txId,
            data.symbol,
            data.action,
            data.price,
            data.volume || data.lot_size || 0.01,
            data.stop_loss || null,
            data.take_profit || null,
            data.atr_at_entry || null
          ]
        );
        break;
      }

      case 'trade.partial_closed': {
        const partialPnl = Number(data.pnl || 0);
        const description = `ปิดบางส่วน ${data.symbol} (Partial PnL: ${partialPnl >= 0 ? '+' : ''}$${partialPnl.toFixed(2)})`;
        const debit = partialPnl >= 0 ? '10100 - เงินสดในบัญชีเทรด' : '50100 - ขาดทุนจากการลงทุน';
        const credit = partialPnl >= 0 ? '40100 - รายได้จากการลงทุน' : '10100 - เงินสดในบัญชีเทรด';

        await client.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, pnl, debit_account, debit_amount, credit_account, credit_amount, trade_id, correlation_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event, description, partialPnl, debit, Math.abs(partialPnl), credit, Math.abs(partialPnl), data.trade_id || txId, correlationId]
        );

        await client.query(
          `UPDATE erp_stats SET accumulated_pnl = accumulated_pnl + $1, last_updated = NOW() WHERE id = 1`,
          [partialPnl]
        );
        break;
      }

      case 'trade.break_even': {
        const description = `Break-even activated for ${data.symbol} @ ${data.price}`;
        await client.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, trade_id, correlation_id)
           VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event, description, data.trade_id || txId, correlationId]
        );

        await client.query(
          `UPDATE trade_positions SET status = 'BREAK_EVEN' WHERE trade_id = $1`,
          [data.trade_id || txId]
        );
        break;
      }

      case 'trade.trailing_activated': {
        const description = `Trailing stop activated for ${data.symbol} @ ${data.price}`;
        await client.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, trade_id, correlation_id)
           VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event, description, data.trade_id || txId, correlationId]
        );

        await client.query(
          `UPDATE trade_positions SET status = 'TRAILING', stop_loss = $2 WHERE trade_id = $1`,
          [data.trade_id || txId, data.new_stop_loss || null]
        );
        break;
      }

      case 'trade.closed':
      case 'trade.pnl_realized': {
        const pnlAmount = Number(data.pnl || 0);
        const feeAmount = Number(data.fee || 0);

        // Update accumulated stats
        await client.query(
          `UPDATE erp_stats SET accumulated_pnl = accumulated_pnl + $1, accumulated_fees = accumulated_fees + $2, last_updated = NOW() WHERE id = 1`,
          [pnlAmount, feeAmount]
        );

        // PnL ledger entry
        const description = pnlAmount >= 0
          ? `กำไรจากการปิดดีล ${data.symbol} (PnL: +$${pnlAmount.toFixed(2)})`
          : `ขาดทุนจากการปิดดีล ${data.symbol} (PnL: $${pnlAmount.toFixed(2)})`;
        const debitAcct = pnlAmount >= 0 ? '10100 - เงินสดในบัญชีเทรด' : '50100 - ขาดทุนจากการลงทุน';
        const creditAcct = pnlAmount >= 0 ? '40100 - รายได้จากการลงทุน' : '10100 - เงินสดในบัญชีเทรด';

        await client.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, pnl, debit_account, debit_amount, credit_account, credit_amount, trade_id, correlation_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event, description, pnlAmount, debitAcct, Math.abs(pnlAmount), creditAcct, Math.abs(pnlAmount), data.trade_id || txId, correlationId]
        );

        // Fee entry
        if (feeAmount > 0) {
          await client.query(
            `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount, trade_id, correlation_id)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT (id) DO NOTHING`,
            [`${txId}_fee`, timestamp, 'fee.recorded',
             `ค่าธรรมเนียมดีล ${data.symbol} ($${feeAmount.toFixed(2)})`,
             '50200 - ค่าธรรมเนียมโบรกเกอร์', feeAmount,
             '10100 - เงินสดในบัญชีเทรด', feeAmount,
             data.trade_id || txId, correlationId]
          );

          // VAT on fee
          const vatOnFee = Number((feeAmount * VAT_RATE).toFixed(2));
          if (vatOnFee > 0) {
            await client.query(
              `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount, trade_id, correlation_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT (id) DO NOTHING`,
              [`${txId}_vat`, timestamp, 'tax.vat_input',
               `ภาษีซื้อ VAT ${VAT_RATE * 100}% บนค่าธรรมเนียม ${data.symbol}`,
               '18100 - ภาษีซื้อ (ขอคืนได้)', vatOnFee,
               '10100 - เงินสดในบัญชีเทรด', vatOnFee,
               data.trade_id || txId, correlationId]
            );
          }
        }

        // Update trade position record
        const existPos = await client.query(
          `SELECT id, entry_price, opened_at FROM trade_positions WHERE trade_id = $1`,
          [data.trade_id || txId]
        );
        if (existPos.rows.length > 0) {
          const entryPrice = existPos.rows[0].entry_price || data.price || 0;
          const exitPrice = data.price || data.exit_price || 0;
          const openedAt = existPos.rows[0].opened_at;
          const closedAt = new Date();
          const durationMins = openedAt
            ? Math.round((closedAt - new Date(openedAt)) / 60000)
            : null;

          const sl = data.stop_loss || (await client.query(
            `SELECT stop_loss FROM trade_positions WHERE trade_id = $1`, [data.trade_id || txId]
          )).rows[0]?.stop_loss || 0;

          const rrRatio = sl && entryPrice && Math.abs(entryPrice - sl) > 0
            ? Math.abs(pnlAmount) / (Math.abs(entryPrice - sl) * (data.lot_size || 0.01))
            : null;

          await client.query(
            `UPDATE trade_positions SET
              exit_price = $2,
              realized_pnl = $3,
              fee = $4,
              rr_ratio = $5,
              duration_minutes = $6,
              closed_at = $7,
              status = 'CLOSED'
             WHERE trade_id = $1`,
            [data.trade_id || txId, exitPrice, pnlAmount, feeAmount, rrRatio, durationMins, closedAt.toISOString()]
          );
        } else {
          // Upsert if position was not opened via ERP (direct close event)
          await client.query(
            `INSERT INTO trade_positions (trade_id, symbol, action, entry_price, exit_price, lot_size, realized_pnl, fee, opened_at, closed_at, status)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW(), 'CLOSED')
             ON CONFLICT (trade_id) DO UPDATE SET
               exit_price = EXCLUDED.exit_price, realized_pnl = EXCLUDED.realized_pnl,
               fee = EXCLUDED.fee, closed_at = EXCLUDED.closed_at, status = 'CLOSED'`,
            [
              data.trade_id || txId,
              data.symbol,
              data.action || 'UNKNOWN',
              data.entry_price || data.price || 0,
              data.price || data.exit_price || 0,
              data.volume || data.lot_size || 0.01,
              pnlAmount,
              feeAmount
            ]
          );
        }
        break;
      }

      case 'fee.recorded': {
        const feeOnly = Number(data.amount || 0);
        await client.query(
          `UPDATE erp_stats SET accumulated_fees = accumulated_fees + $1, last_updated = NOW() WHERE id = 1`,
          [feeOnly]
        );
        await client.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount, correlation_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event,
           `ค่าธรรมเนียม: ${data.description || 'ไม่มีรายละเอียด'} ($${feeOnly})`,
           '50200 - ค่าธรรมเนียมโบรกเกอร์', feeOnly,
           '10100 - เงินสดในบัญชีเทรด', feeOnly,
           correlationId]
        );
        break;
      }

      default:
        await client.query('ROLLBACK');
        return res.status(400).json({ success: false, error: `Unknown event type: ${event}` });
    }

    // Mark idempotency record as processed
    await markDelivery(client, idempotencyKey, event, req.body, 'SUCCESS', 200);

    await client.query('COMMIT');

    const statsRes = await pool.query('SELECT accumulated_pnl FROM erp_stats WHERE id = 1');
    const ledgerCount = await pool.query('SELECT count(*) as c FROM erp_ledger');

    await logAudit(req, 'WEBHOOK_PROCESSED', { event, txId });

    return res.json({
      success: true,
      message: 'บันทึกข้อมูลเข้าสู่ระบบ ERP Ledger เรียบร้อย',
      txId,
      event,
      totalPnL: Number((statsRes.rows[0]?.accumulated_pnl || 0).toFixed(2)),
      ledgerEntries: parseInt(ledgerCount.rows[0].c),
      correlationId
    });

  } catch (err) {
    await client.query('ROLLBACK');
    if (idempotencyKey) {
      try { await markDelivery(client, idempotencyKey, event, req.body, 'ERROR', 500); } catch {}
    }
    console.error(`[ERP][${correlationId}] Webhook error:`, err.message);
    await logAudit(req, 'WEBHOOK_ERROR', { event, error: err.message });
    return res.status(500).json({ success: false, error: err.message, correlationId });
  } finally {
    client.release();
  }
}

// ─────────────────────────────────────────────────────────
// GET /api/ledger
// ─────────────────────────────────────────────────────────
export async function getLedger(req, res) {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = Math.min(200, parseInt(req.query.limit) || 50);
  const offset = (page - 1) * limit;
  const { event: filterEvent, from, to } = req.query;

  try {
    let whereClause = '';
    const params = [limit, offset];
    const conditions = [];

    if (filterEvent) { params.push(filterEvent); conditions.push(`event = $${params.length}`); }
    if (from) { params.push(from); conditions.push(`timestamp >= $${params.length}`); }
    if (to) { params.push(to); conditions.push(`timestamp <= $${params.length}`); }
    if (conditions.length) whereClause = 'WHERE ' + conditions.join(' AND ');

    const countRes = await pool.query(`SELECT count(*) as c FROM erp_ledger ${whereClause}`, params.slice(2));
    const rowsRes = await pool.query(
      `SELECT * FROM erp_ledger ${whereClause} ORDER BY timestamp DESC LIMIT $1 OFFSET $2`,
      params
    );
    const statsRes = await pool.query('SELECT last_updated FROM erp_stats WHERE id = 1');

    return res.json({
      success: true,
      ledger: rowsRes.rows.map(r => ({
        id: r.id,
        timestamp: r.timestamp,
        event: r.event,
        description: r.description,
        pnl: r.pnl,
        trade_id: r.trade_id,
        debit: { account: r.debit_account, amount: r.debit_amount },
        credit: { account: r.credit_account, amount: r.credit_amount }
      })),
      total: parseInt(countRes.rows[0].c),
      page,
      limit,
      lastUpdated: statsRes.rows[0]?.last_updated
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}

// ─────────────────────────────────────────────────────────
// GET /api/tax-summary
// ─────────────────────────────────────────────────────────
export async function getTaxSummary(req, res) {
  try {
    const statsRes = await pool.query('SELECT * FROM erp_stats WHERE id = 1');
    const stats = statsRes.rows[0] || { accumulated_fees: 0, accumulated_pnl: 0 };

    const pnl = stats.accumulated_pnl;
    const fees = stats.accumulated_fees;
    const taxableIncome = Math.max(0, pnl - fees);

    return res.json({
      success: true,
      data: {
        accumulatedPnL: Number(pnl.toFixed(2)),
        accumulatedFees: Number(fees.toFixed(2)),
        taxableIncome: Number(taxableIncome.toFixed(2)),
        vatRate: `${VAT_RATE * 100}%`,
        inputVatClaimable: Number((fees * VAT_RATE).toFixed(2)),
        corporateTaxRate: `${CORPORATE_TAX_RATE * 100}%`,
        estimatedIncomeTax: Number((taxableIncome * CORPORATE_TAX_RATE).toFixed(2)),
        netAfterTax: Number((taxableIncome * (1 - CORPORATE_TAX_RATE)).toFixed(2)),
        lastUpdated: stats.last_updated
      }
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}

// ─────────────────────────────────────────────────────────
// GET /api/summary
// ─────────────────────────────────────────────────────────
export async function getSummary(req, res) {
  try {
    const [tradesRes, statsRes, ledgerCountRes] = await Promise.all([
      pool.query(`SELECT realized_pnl FROM trade_positions WHERE status = 'CLOSED'`),
      pool.query('SELECT * FROM erp_stats WHERE id = 1'),
      pool.query('SELECT count(*) as c FROM erp_ledger')
    ]);

    const trades = tradesRes.rows;
    const stats = statsRes.rows[0] || { accumulated_fees: 0, accumulated_pnl: 0 };
    const wins = trades.filter(t => (t.realized_pnl || 0) > 0).length;
    const losses = trades.filter(t => (t.realized_pnl || 0) <= 0).length;

    const openRes = await pool.query(`SELECT count(*) as c FROM trade_positions WHERE status NOT IN ('CLOSED')`);

    return res.json({
      success: true,
      summary: {
        totalTrades: trades.length + parseInt(openRes.rows[0].c),
        closedTrades: trades.length,
        openTrades: parseInt(openRes.rows[0].c),
        winTrades: wins,
        lossTrades: losses,
        winRate: trades.length > 0 ? Number(((wins / trades.length) * 100).toFixed(1)) : 0,
        totalPnL: Number(stats.accumulated_pnl.toFixed(2)),
        totalFees: Number(stats.accumulated_fees.toFixed(2)),
        netPnL: Number((stats.accumulated_pnl - stats.accumulated_fees).toFixed(2)),
        ledgerEntries: parseInt(ledgerCountRes.rows[0].c),
        lastUpdated: stats.last_updated
      }
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}

// ─────────────────────────────────────────────────────────
// GET /api/open-positions
// ─────────────────────────────────────────────────────────
export async function getOpenPositions(req, res) {
  try {
    const res2 = await pool.query(
      `SELECT trade_id, symbol, action, entry_price, lot_size, stop_loss, take_profit, opened_at, status
       FROM trade_positions
       WHERE status NOT IN ('CLOSED')
       ORDER BY opened_at DESC`
    );

    // Calculate unrealized PnL placeholder (no live price available in ERP; return null)
    const positions = res2.rows.map(p => ({
      tradeId: p.trade_id,
      symbol: p.symbol,
      action: p.action,
      entry: p.entry_price,
      lot: p.lot_size,
      sl: p.stop_loss,
      tp: p.take_profit,
      status: p.status,
      openedAt: p.opened_at,
      unrealizedPnl: null // calculated by trading backend
    }));

    return res.json({ success: true, positions, total: positions.length });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}

// ─────────────────────────────────────────────────────────
// GET /api/trades
// ─────────────────────────────────────────────────────────
export async function getTrades(req, res) {
  const { from, to, symbol, status: filterStatus } = req.query;
  try {
    const conditions = [];
    const params = [];

    if (from) { params.push(from); conditions.push(`opened_at >= $${params.length}`); }
    if (to) { params.push(to); conditions.push(`opened_at <= $${params.length}`); }
    if (symbol) { params.push(symbol.toUpperCase()); conditions.push(`symbol = $${params.length}`); }
    if (filterStatus) { params.push(filterStatus.toUpperCase()); conditions.push(`status = $${params.length}`); }

    const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';
    const tradesRes = await pool.query(
      `SELECT * FROM trade_positions ${where} ORDER BY opened_at DESC LIMIT 500`,
      params
    );

    const trades = tradesRes.rows.map(t => ({
      tradeId: t.trade_id,
      symbol: t.symbol,
      action: t.action,
      entry: t.entry_price,
      exit: t.exit_price,
      lot: t.lot_size,
      sl: t.stop_loss,
      tp: t.take_profit,
      realizedPnl: t.realized_pnl,
      fee: t.fee,
      rrRatio: t.rr_ratio,
      durationMinutes: t.duration_minutes,
      result: t.realized_pnl > 0 ? 'WIN' : t.realized_pnl < 0 ? 'LOSS' : 'BREAK_EVEN',
      openedAt: t.opened_at,
      closedAt: t.closed_at,
      status: t.status
    }));

    return res.json({ success: true, trades, total: trades.length });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}

// ─────────────────────────────────────────────────────────
// GET /api/performance
// ─────────────────────────────────────────────────────────
export async function getPerformance(req, res) {
  try {
    const tradesRes = await pool.query(
      `SELECT realized_pnl, rr_ratio, fee FROM trade_positions WHERE status = 'CLOSED'`
    );
    const trades = tradesRes.rows;

    if (trades.length === 0) {
      return res.json({
        success: true,
        performance: {
          winRate: 0, profitFactor: 0, averageRR: 0,
          expectancy: 0, maxDrawdown: 0,
          totalTrades: 0, winningTrades: 0, losingTrades: 0
        }
      });
    }

    const wins = trades.filter(t => (t.realized_pnl || 0) > 0);
    const losses = trades.filter(t => (t.realized_pnl || 0) < 0);

    const grossProfit = wins.reduce((s, t) => s + (t.realized_pnl || 0), 0);
    const grossLoss = Math.abs(losses.reduce((s, t) => s + (t.realized_pnl || 0), 0));
    const winRate = Number(((wins.length / trades.length) * 100).toFixed(2));
    const profitFactor = grossLoss > 0 ? Number((grossProfit / grossLoss).toFixed(3)) : grossProfit > 0 ? 999 : 0;

    const rrValues = trades.filter(t => t.rr_ratio !== null).map(t => t.rr_ratio);
    const averageRR = rrValues.length > 0
      ? Number((rrValues.reduce((s, v) => s + v, 0) / rrValues.length).toFixed(3))
      : 0;

    const avgWin = wins.length > 0 ? grossProfit / wins.length : 0;
    const avgLoss = losses.length > 0 ? grossLoss / losses.length : 0;
    const winRateFrac = wins.length / trades.length;
    const expectancy = Number(((winRateFrac * avgWin) - ((1 - winRateFrac) * avgLoss)).toFixed(2));

    // Max drawdown calculation
    let peak = 0, equity = 0, maxDrawdown = 0;
    for (const t of trades) {
      equity += (t.realized_pnl || 0);
      if (equity > peak) peak = equity;
      const dd = peak > 0 ? ((peak - equity) / peak) * 100 : 0;
      if (dd > maxDrawdown) maxDrawdown = dd;
    }

    return res.json({
      success: true,
      performance: {
        winRate,
        profitFactor,
        averageRR,
        expectancy,
        maxDrawdown: Number(maxDrawdown.toFixed(2)),
        totalTrades: trades.length,
        winningTrades: wins.length,
        losingTrades: losses.length
      }
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}

// ─────────────────────────────────────────────────────────
// GET /metrics — Prometheus-style operational metrics
// ─────────────────────────────────────────────────────────
export async function getMetrics(req, res) {
  try {
    const [statsRes, tradesRes, openRes, failedDelivRes] = await Promise.all([
      pool.query('SELECT * FROM erp_stats WHERE id = 1'),
      pool.query(`SELECT realized_pnl, rr_ratio FROM trade_positions WHERE status = 'CLOSED'`),
      pool.query(`SELECT count(*) as c FROM trade_positions WHERE status NOT IN ('CLOSED')`),
      pool.query(`SELECT count(*) as c FROM erp_delivery_records WHERE status IN ('ERROR', 'FAILED')`)
    ]);

    const stats = statsRes.rows[0] || { accumulated_pnl: 0, accumulated_fees: 0 };
    const closed = tradesRes.rows;
    const wins = closed.filter(t => (t.realized_pnl || 0) > 0).length;
    const rrVals = closed.filter(t => t.rr_ratio).map(t => t.rr_ratio);

    return res.json({
      success: true,
      metrics: {
        totalTrades: closed.length,
        openTrades: parseInt(openRes.rows[0].c),
        winRate: closed.length > 0 ? Number(((wins / closed.length) * 100).toFixed(2)) : 0,
        totalPnL: Number(stats.accumulated_pnl.toFixed(2)),
        totalFees: Number(stats.accumulated_fees.toFixed(2)),
        netPnL: Number((stats.accumulated_pnl - stats.accumulated_fees).toFixed(2)),
        averageRR: rrVals.length > 0 ? Number((rrVals.reduce((a, b) => a + b, 0) / rrVals.length).toFixed(3)) : 0,
        deliveryFailures: parseInt(failedDelivRes.rows[0].c),
        uptime: process.uptime()
      }
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}

// ─────────────────────────────────────────────────────────
// DELETE /api/reset — dev only
// ─────────────────────────────────────────────────────────
export async function resetERP(req, res) {
  if (process.env.NODE_ENV !== 'development') {
    return res.status(403).json({ success: false, error: 'Reset is forbidden in non-development environments.' });
  }

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM erp_ledger');
    await client.query('DELETE FROM trade_positions');
    await client.query('DELETE FROM erp_delivery_records');
    await client.query(`UPDATE erp_stats SET accumulated_fees = 0, accumulated_pnl = 0, last_updated = NOW() WHERE id = 1`);
    await client.query(
      `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount)
       VALUES ('tx_reset', NOW(), 'system.reset', 'รีเซ็ตระบบ ERP Ledger', '10100 - เงินสด', 0, '30100 - ทุน', 0)
       ON CONFLICT (id) DO UPDATE SET timestamp = NOW()`
    );
    await client.query('COMMIT');
    return res.json({ success: true, message: 'ERP รีเซ็ตฐานข้อมูล PostgreSQL เรียบร้อย' });
  } catch (err) {
    await client.query('ROLLBACK');
    return res.status(500).json({ success: false, error: err.message });
  } finally {
    client.release();
  }
}
