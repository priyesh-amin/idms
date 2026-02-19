const express = require('express');
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const cors = require('cors');
const { spawn } = require('child_process');
const audit = require('./audit');
const db = require('./db');
require('dotenv').config();

const app = express();
app.use(express.json());
app.use(cors());

const PORT = process.env.PORT || 5000;
const RAW_MODE = process.env.IDMS_EXECUTION_MODE || 'observe';
const EXECUTION_MODE = RAW_MODE.toLowerCase() === 'live' ? 'live' : 'observe';

const IS_WINDOWS = process.platform === 'win32';
const DEFAULT_BASE_IDMS = IS_WINDOWS
  ? 'g:\\My Drive\\Priyesh-life-os\\00-daily-ops\\scripts\\idms'
  : path.resolve(__dirname, '../../..');

const BASE_IDMS = path.resolve(process.env.BASE_IDMS || DEFAULT_BASE_IDMS);
const INBOX_PATH = path.resolve(
  process.env.IDMS_INBOX_PATH ||
    (IS_WINDOWS
      ? 'g:\\My Drive\\Priyesh-life-os\\00-daily-ops\\Inbox'
      : path.join(BASE_IDMS, '00-daily-ops', 'Inbox'))
);
const REVIEW_PATH = path.resolve(
  process.env.IDMS_REVIEW_PATH ||
    (IS_WINDOWS
      ? 'g:\\My Drive\\Priyesh-life-os\\00-daily-ops\\Inbox\\review'
      : path.join(BASE_IDMS, '00-daily-ops', 'Inbox', 'review'))
);
const PROCESSING_PATH = path.resolve(process.env.PROCESSING_PATH || path.join(BASE_IDMS, 'processing'));
const STAGING_PATH = path.join(PROCESSING_PATH, 'staging');
const WORKING_PATH = path.join(PROCESSING_PATH, 'working');
const ERROR_PATH = path.join(PROCESSING_PATH, 'error');
const FINAL_PATH = path.resolve(
  process.env.IDMS_FINAL_PATH ||
    (IS_WINDOWS
      ? 'g:\\My Drive\\Priyesh-life-os\\06-long-term-memory'
      : path.join(BASE_IDMS, '06-long-term-memory'))
);
const LOG_PATH = path.resolve(
  process.env.IDMS_LOG_PATH || path.join(BASE_IDMS, 'backend', 'logs', 'idms-audit.log')
);

const PYTHON_PATH = process.env.PYTHON_PATH || (IS_WINDOWS ? 'python' : 'python3');
const PIPELINE_RUNNER_PATH = process.env.PIPELINE_RUNNER_PATH || path.resolve(__dirname, '../pipelines/pipeline_runner.py');
const PYTHON_TIMEOUT_MS = parseInt(process.env.PYTHON_TIMEOUT_MS || '30000', 10);
const MAX_FILE_SIZE_MB = parseInt(process.env.MAX_FILE_SIZE_MB || '50', 10);
const FILE_REGEX = new RegExp(process.env.ALLOWED_FILE_REGEX || '^[a-zA-Z0-9_\\-\\.]+\\.pdf$');

const executionRegistry = new Map();
const lastActionTimes = new Map();
const ipRequests = new Map();

function ensureDirectories() {
  [PROCESSING_PATH, STAGING_PATH, WORKING_PATH, ERROR_PATH, path.dirname(LOG_PATH)].forEach((dir) => {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  });
}
ensureDirectories();

if (EXECUTION_MODE === 'live' && (!PIPELINE_RUNNER_PATH || !fs.existsSync(PIPELINE_RUNNER_PATH))) {
  console.error('FATAL: PIPELINE_RUNNER_PATH invalid');
  process.exit(1);
}

try {
  audit.verifyChain(LOG_PATH);

  const orphanedStaging = fs.existsSync(STAGING_PATH)
    ? fs.readdirSync(STAGING_PATH).filter((f) => f.endsWith('.tmp'))
    : [];

  orphanedStaging.forEach((filename) => {
    const execution_id = filename.replace('.tmp', '');
    const src = path.join(STAGING_PATH, filename);
    const dest = path.join(ERROR_PATH, filename);
    fs.renameSync(src, dest);

    audit.appendEntry(LOG_PATH, {
      execution_id,
      status: 'RECOVERY',
      mode: EXECUTION_MODE,
      timestamp: new Date().toISOString(),
      outcome: 'INTERRUPTED',
      failure_category: 'SYSTEM_RECOVERY',
      errors: ['ORPHAN_STAGING_TMP', 'HASH_UNKNOWN'],
      file: dest,
    });
    console.log(`[GOVERNOR] Audited and quarantined staging orphan: ${execution_id}`);
  });

  audit.recoverOrphans(LOG_PATH, EXECUTION_MODE);
} catch (e) {
  console.error(`FATAL: Startup integrity check failed: ${e.message}`);
  process.exit(1);
}

function checkRateLimit(ip) {
  const now = Date.now();
  let entry = ipRequests.get(ip);
  if (!entry || now - entry.windowStart > 60000) entry = { count: 1, windowStart: now };
  else entry.count += 1;
  ipRequests.set(ip, entry);
  return entry.count <= (parseInt(process.env.IDMS_RATE_LIMIT_PER_MIN || '60', 10));
}

function calculateFileHash(filePath) {
  try {
    return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
  } catch {
    return null;
  }
}

function handleTerminalOutcome(
  execution_id,
  status,
  outcome,
  failureCategory,
  exitCode,
  runtime,
  errors,
  stdout,
  stderr,
  absPath,
  lockPath,
  hashBefore
) {
  audit.appendEntry(LOG_PATH, {
    execution_id,
    status,
    outcome,
    failure_category: failureCategory,
    exit_code: exitCode,
    runtime_ms: runtime,
    errors,
    stdout_snippet: stdout,
    stderr_snippet: stderr,
    file: absPath,
    file_hash_before: hashBefore,
  });

  const filename = path.basename(absPath);
  const workingPath = path.join(WORKING_PATH, filename);
  const dest = status === 'COMPLETED_SUCCESS' ? path.join(FINAL_PATH, filename) : path.join(ERROR_PATH, filename);
  if (fs.existsSync(workingPath)) {
    try {
      fs.renameSync(workingPath, dest);
    } catch (e) {
      console.error(`[GOVERNOR] Move to final/error failed: ${e.message}`);
    }
  }
  executionRegistry.delete(lockPath);
}

async function requireDb(res) {
  const ok = await db.healthCheck();
  if (!ok) {
    res.status(503).json({
      error_code: 'DB_UNAVAILABLE',
      message: 'Postgres is not reachable. Verify docker services and DB env vars.',
    });
    return false;
  }
  return true;
}

app.get('/api/status', (req, res) =>
  res.json({ status: 'READY', mode: EXECUTION_MODE, timestamp: new Date().toISOString() })
);

app.get('/api/db/health', async (req, res) => {
  const ok = await db.healthCheck();
  res.json({ ok });
});

app.get('/api/audit/:execution_id', (req, res) => {
  const entry = audit.getLatestEntryByExecutionId(LOG_PATH, req.params.execution_id);
  if (!entry) return res.status(404).json({ error_code: 'FILE_NOT_FOUND', message: 'ID not found' });
  const terminal = ['COMPLETED_SUCCESS', 'COMPLETED_FAILURE', 'TIMEOUT', 'RECOVERY'];
  return res.json({ execution_id: req.params.execution_id, isTerminal: terminal.includes(entry.status), entry });
});

app.get('/api/files', (req, res) => {
  try {
    const files = fs.existsSync(INBOX_PATH) ? fs.readdirSync(INBOX_PATH).filter((f) => FILE_REGEX.test(f)) : [];
    res.json({ files });
  } catch {
    res.status(500).json({ error_code: 'INTERNAL_FAILURE', message: 'Inbox error' });
  }
});

app.get('/api/query/invoices', async (req, res) => {
  if (!(await requireDb(res))) return;

  const now = new Date();
  const year = parseInt(req.query.year || `${now.getUTCFullYear()}`, 10);
  const q4Min = parseFloat(req.query.q4Min || '5000');

  try {
    const result = await db.query(
      `
      SELECT
        i.doc_id,
        i.invoice_number,
        i.invoice_date,
        i.due_date,
        i.currency,
        i.total_amount,
        i.vat_amount,
        i.vat_reclaimable,
        COALESCE(i.vendor, d.entity) AS vendor,
        d.source_file
      FROM invoices i
      LEFT JOIN documents d ON d.doc_id = i.doc_id
      WHERE i.invoice_date >= make_date($1, 10, 1)
        AND i.invoice_date < make_date($1 + 1, 1, 1)
        AND COALESCE(i.total_amount, 0) >= $2
      ORDER BY i.total_amount DESC NULLS LAST
      `,
      [year, q4Min]
    );

    const totalAmount = result.rows.reduce((sum, row) => sum + Number(row.total_amount || 0), 0);
    res.json({
      filter: { year, q4Min },
      count: result.rows.length,
      totalAmount,
      rows: result.rows,
    });
  } catch (err) {
    res.status(500).json({ error_code: 'QUERY_FAILED', message: err.message });
  }
});

app.get('/api/query/vat-reclaimable', async (req, res) => {
  if (!(await requireDb(res))) return;

  const now = new Date();
  const defaultFrom = `${now.getUTCFullYear()}-01-01`;
  const defaultTo = now.toISOString().slice(0, 10);

  const dateFrom = String(req.query.dateFrom || defaultFrom);
  const dateTo = String(req.query.dateTo || defaultTo);

  try {
    const result = await db.query(
      `
      SELECT
        i.doc_id,
        i.invoice_number,
        i.invoice_date,
        i.currency,
        i.vat_reclaimable,
        COALESCE(i.vendor, d.entity) AS vendor
      FROM invoices i
      LEFT JOIN documents d ON d.doc_id = i.doc_id
      WHERE i.invoice_date BETWEEN $1::date AND $2::date
        AND COALESCE(i.vat_reclaimable, 0) > 0
      ORDER BY i.invoice_date DESC
      `,
      [dateFrom, dateTo]
    );

    const vatReclaimableTotal = result.rows.reduce(
      (sum, row) => sum + Number(row.vat_reclaimable || 0),
      0
    );

    res.json({
      filter: { dateFrom, dateTo },
      count: result.rows.length,
      vatReclaimableTotal,
      rows: result.rows,
    });
  } catch (err) {
    res.status(500).json({ error_code: 'QUERY_FAILED', message: err.message });
  }
});

app.get('/api/query/ar-overdue', async (req, res) => {
  if (!(await requireDb(res))) return;

  try {
    const result = await db.query(`
      WITH merged AS (
        SELECT
          COALESCE(a.doc_id, i.doc_id) AS doc_id,
          COALESCE(a.counterparty, i.customer, i.vendor) AS counterparty,
          COALESCE(a.due_date, i.due_date) AS due_date,
          COALESCE(a.amount_outstanding, i.total_amount, 0) AS amount_outstanding,
          LOWER(COALESCE(a.status, i.payment_status, 'open')) AS status
        FROM invoices i
        FULL OUTER JOIN ar_items a ON a.doc_id = i.doc_id
      )
      SELECT *
      FROM merged
      WHERE due_date IS NOT NULL
        AND due_date < CURRENT_DATE
        AND amount_outstanding > 0
        AND status NOT IN ('paid', 'closed')
      ORDER BY due_date ASC
    `);

    const totalOutstanding = result.rows.reduce(
      (sum, row) => sum + Number(row.amount_outstanding || 0),
      0
    );

    res.json({
      asOf: new Date().toISOString(),
      count: result.rows.length,
      totalOutstanding,
      rows: result.rows,
    });
  } catch (err) {
    res.status(500).json({ error_code: 'QUERY_FAILED', message: err.message });
  }
});

app.post('/api/rag/search', async (req, res) => {
  if (!(await requireDb(res))) return;

  const q = String(req.body?.query || '').trim();
  if (!q) {
    return res.status(400).json({ error_code: 'INVALID_REQUEST', message: 'query is required' });
  }

  const requestedTopK = parseInt(req.body?.topK || process.env.IDMS_RAG_DEFAULT_TOP_K || '5', 10);
  const topK = Number.isFinite(requestedTopK) ? Math.max(1, Math.min(requestedTopK, 50)) : 5;

  try {
    let rows = [];

    try {
      const chunkResult = await db.query(
        `
        WITH ranked AS (
          SELECT
            c.doc_id,
            c.chunk_index,
            c.chunk_text,
            similarity(c.chunk_text, $1) AS score
          FROM document_chunks c
          ORDER BY score DESC
          LIMIT $2
        )
        SELECT
          r.doc_id,
          r.chunk_index,
          r.chunk_text,
          r.score,
          d.category,
          d.entity,
          d.storage_path
        FROM ranked r
        LEFT JOIN documents d ON d.doc_id = r.doc_id
        WHERE r.score > 0
        ORDER BY r.score DESC
        `,
        [q, topK]
      );
      rows = chunkResult.rows;
    } catch {
      rows = [];
    }

    if (rows.length === 0) {
      const fallback = await db.query(
        `
        SELECT
          d.doc_id,
          NULL::int AS chunk_index,
          LEFT(d.extracted_text, 1200) AS chunk_text,
          similarity(COALESCE(d.extracted_text, ''), $1) AS score,
          d.category,
          d.entity,
          d.storage_path
        FROM documents d
        ORDER BY score DESC
        LIMIT $2
        `,
        [q, topK]
      );
      rows = fallback.rows.filter((r) => Number(r.score) > 0);
    }

    return res.json({ query: q, topK, count: rows.length, rows });
  } catch (err) {
    return res.status(500).json({ error_code: 'QUERY_FAILED', message: err.message });
  }
});

const handleExecutionRequest = async (req, res, sourceDir) => {
  if (!checkRateLimit(req.ip)) {
    return res.status(429).json({ error_code: 'RATE_LIMITED', message: 'Rate limit exceeded' });
  }

  const { filename, confirm } = req.body;
  if (confirm !== true) {
    return res.status(403).json({ error_code: 'GOVERNANCE_BLOCKED', message: 'Confirm required' });
  }

  if (!filename || !FILE_REGEX.test(filename)) {
    return res.status(400).json({ error_code: 'INVALID_RESOURCE', message: 'Invalid name' });
  }

  const absPath = path.resolve(sourceDir, filename);
  if (!absPath.startsWith(sourceDir) || !fs.existsSync(absPath)) {
    return res.status(404).json({ error_code: 'FILE_NOT_FOUND', message: 'File missing' });
  }

  if (fs.statSync(absPath).size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    return res
      .status(400)
      .json({ error_code: 'INVALID_RESOURCE', message: `File size exceeds ${MAX_FILE_SIZE_MB}MB limit` });
  }

  if (executionRegistry.has(absPath)) {
    return res.status(423).json({ error_code: 'RESOURCE_LOCKED', message: 'File is being processed' });
  }

  const lastTime = lastActionTimes.get(absPath) || 0;
  if (Date.now() - lastTime < 5000) {
    return res.status(429).json({ error_code: 'COOLDOWN_ACTIVE', message: 'Cooldown active (5s)' });
  }

  const execution_id = uuidv4();
  executionRegistry.set(absPath, execution_id);
  lastActionTimes.set(absPath, Date.now());

  const hash = calculateFileHash(absPath);
  const startTime = Date.now();

  if (!hash) {
    executionRegistry.delete(absPath);
    return res.status(500).json({ error_code: 'INTERNAL_FAILURE', message: 'Hash calculation failed' });
  }

  let startEntry;
  try {
    startEntry = audit.appendEntry(LOG_PATH, {
      execution_id,
      status: 'STARTED',
      mode: EXECUTION_MODE,
      timestamp: new Date().toISOString(),
      file: absPath,
      file_hash_before: hash,
    });
  } catch (e) {
    executionRegistry.delete(absPath);
    return res.status(503).json({ error_code: 'INTEGRITY_VIOLATION', message: `Audit append failed: ${e.message}` });
  }

  if (EXECUTION_MODE === 'observe') {
    const completion = audit.appendEntry(LOG_PATH, {
      execution_id,
      status: 'COMPLETED_SUCCESS',
      mode: EXECUTION_MODE,
      timestamp: new Date().toISOString(),
      file: absPath,
      file_hash_before: hash,
      outcome: 'SIMULATED',
      runtime_ms: Date.now() - startTime,
    });
    executionRegistry.delete(absPath);
    return res.status(202).json({ message: 'Authorized', execution_id, audit_entry: completion });
  }

  try {
    const stagingPath = path.join(STAGING_PATH, `${execution_id}.tmp`);
    fs.renameSync(absPath, stagingPath);
    const workingPath = path.join(WORKING_PATH, filename);
    fs.renameSync(stagingPath, workingPath);

    const child = spawn(PYTHON_PATH, [PIPELINE_RUNNER_PATH, '--file', workingPath], {
      shell: false,
      cwd: BASE_IDMS,
      env: { ...process.env, NODE_ENV: 'production' },
    });

    audit.appendEntry(LOG_PATH, {
      execution_id,
      status: 'EXECUTING',
      mode: EXECUTION_MODE,
      timestamp: new Date().toISOString(),
      file: absPath,
      file_hash_before: hash,
      pid: child.pid,
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => {
      stdout += d.toString();
    });
    child.stderr.on('data', (d) => {
      stderr += d.toString();
    });

    const timeout = setTimeout(() => {
      child.kill('SIGKILL');
      handleTerminalOutcome(
        execution_id,
        'TIMEOUT',
        'TIMEOUT',
        'TIMEOUT',
        -1,
        PYTHON_TIMEOUT_MS,
        ['Timeout'],
        stdout,
        stderr,
        absPath,
        absPath,
        hash
      );
    }, PYTHON_TIMEOUT_MS);

    child.on('close', (code) => {
      clearTimeout(timeout);
      const runtime = Date.now() - startTime;
      if (code === 0) {
        handleTerminalOutcome(
          execution_id,
          'COMPLETED_SUCCESS',
          'SUCCESS',
          'NONE',
          0,
          runtime,
          [],
          stdout,
          stderr,
          absPath,
          absPath,
          hash
        );
      } else {
        handleTerminalOutcome(
          execution_id,
          'COMPLETED_FAILURE',
          'FAILURE',
          'RUNTIME_ERROR',
          code,
          runtime,
          [`Exit ${code}`],
          stdout,
          stderr,
          absPath,
          absPath,
          hash
        );
      }
    });

    return res.status(202).json({ message: 'Authorized', execution_id, audit_entry: startEntry });
  } catch (err) {
    handleTerminalOutcome(
      execution_id,
      'COMPLETED_FAILURE',
      'FAILURE',
      'FILE_SYSTEM_ERROR',
      -1,
      Date.now() - startTime,
      [err.message],
      '',
      '',
      absPath,
      absPath,
      hash
    );
    return res.status(500).json({
      error_code: 'INTERNAL_FAILURE',
      message: `Filesystem error: ${err.message}`,
      execution_id,
      last_audit_entry: audit.getLatestEntryByExecutionId(LOG_PATH, execution_id),
    });
  }
};

app.post('/api/process', (req, res) => handleExecutionRequest(req, res, INBOX_PATH));
app.post('/api/finalize', (req, res) => handleExecutionRequest(req, res, REVIEW_PATH));

app.listen(PORT, () => {
  console.log(`[GOVERNOR] Running on ${PORT}`);
});
