const express = require('express');
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const cors = require('cors');
const { spawn } = require('child_process');
const audit = require('./audit');
require('dotenv').config();

const app = express();
app.use(express.json());
app.use(cors());

// --- GOVERNANCE CONFIGURATION (ARC-006) ---
const PORT = process.env.PORT || 5000;
const RAW_MODE = process.env.IDMS_EXECUTION_MODE || 'observe';
const EXECUTION_MODE = (RAW_MODE.toLowerCase() === 'live') ? 'live' : 'observe';

// Canonical Paths
const BASE_IDMS = path.resolve(process.env.BASE_IDMS || 'g:\\My Drive\\Priyesh-life-os\\00-daily-ops\\scripts\\idms');
const INBOX_PATH = path.resolve(process.env.IDMS_INBOX_PATH || 'g:\\My Drive\\Priyesh-life-os\\00-daily-ops\\Inbox');
const REVIEW_PATH = path.resolve(process.env.IDMS_REVIEW_PATH || 'g:\\My Drive\\Priyesh-life-os\\00-daily-ops\\Inbox\\review');
const PROCESSING_PATH = path.resolve(process.env.PROCESSING_PATH || path.join(BASE_IDMS, 'processing'));
const STAGING_PATH = path.join(PROCESSING_PATH, 'staging');
const WORKING_PATH = path.join(PROCESSING_PATH, 'working');
const ERROR_PATH = path.join(PROCESSING_PATH, 'error');
const FINAL_PATH = path.resolve(process.env.IDMS_FINAL_PATH || 'g:\\My Drive\\Priyesh-life-os\\06-long-term-memory');
const LOG_PATH = path.resolve(process.env.IDMS_LOG_PATH || path.join(BASE_IDMS, 'logs', 'idms-audit.log'));

// Execution Config
const PYTHON_PATH = process.env.PYTHON_PATH || 'python';
const PIPELINE_RUNNER_PATH = process.env.PIPELINE_RUNNER_PATH;
const PYTHON_TIMEOUT_MS = parseInt(process.env.PYTHON_TIMEOUT_MS || '30000', 10);
const MAX_FILE_SIZE_MB = parseInt(process.env.MAX_FILE_SIZE_MB || '50', 10);
const FILE_REGEX = new RegExp(process.env.ALLOWED_FILE_REGEX || '^[a-zA-Z0-9_\\-\\.]+\\.pdf$');

// --- CONCURRENCY & RATE LIMITING STATE ---
const executionRegistry = new Map(); // absPath -> execution_id
const lastActionTimes = new Map(); // absPath -> timestamp
const ipRequests = new Map(); // ip -> { count, windowStart }

// --- STARTUP CHECKS ---
function ensureDirectories() {
    [PROCESSING_PATH, STAGING_PATH, WORKING_PATH, ERROR_PATH, path.dirname(LOG_PATH)].forEach(dir => {
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    });
}
ensureDirectories();

if (EXECUTION_MODE === 'live' && (!PIPELINE_RUNNER_PATH || !fs.existsSync(PIPELINE_RUNNER_PATH))) {
    console.error(`FATAL: PIPELINE_RUNNER_PATH invalid`);
    process.exit(1);
}

try {
    audit.verifyChain(LOG_PATH);

    // Clean staging of orphans on startup with full audit trail (BLD-LIVE-003)
    const orphanedStaging = fs.readdirSync(STAGING_PATH).filter(f => f.endsWith('.tmp'));
    orphanedStaging.forEach(filename => {
        const execution_id = filename.replace('.tmp', '');
        const src = path.join(STAGING_PATH, filename);
        const dest = path.join(ERROR_PATH, filename);
        fs.renameSync(src, dest);

        audit.appendEntry(LOG_PATH, {
            execution_id,
            status: "RECOVERY",
            mode: EXECUTION_MODE,
            timestamp: new Date().toISOString(),
            outcome: "INTERRUPTED",
            failure_category: "SYSTEM_RECOVERY",
            errors: ["ORPHAN_STAGING_TMP", "HASH_UNKNOWN"],
            file: dest
        });
        console.log(`[GOVERNOR] Audited and quarantined staging orphan: ${execution_id}`);
    });

    audit.recoverOrphans(LOG_PATH, EXECUTION_MODE);
} catch (e) {
    console.error(`FATAL: Startup integrity check failed: ${e.message}`);
    process.exit(1);
}

// --- HELPERS ---

function checkRateLimit(ip) {
    const now = Date.now();
    let entry = ipRequests.get(ip);
    if (!entry || (now - entry.windowStart) > 60000) entry = { count: 1, windowStart: now };
    else entry.count++;
    ipRequests.set(ip, entry);
    return entry.count <= (parseInt(process.env.IDMS_RATE_LIMIT_PER_MIN) || 60);
}

function calculateFileHash(filePath) {
    try {
        return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
    } catch (e) { return null; }
}

function handleTerminalOutcome(execution_id, status, outcome, failureCategory, exitCode, runtime, errors, stdout, stderr, absPath, lockPath, hashBefore) {
    // BLD-LIVE-003: Preserve file_hash_before from parameter
    audit.appendEntry(LOG_PATH, {
        execution_id, status, outcome, failure_category: failureCategory, exit_code: exitCode,
        runtime_ms: runtime, errors, stdout_snippet: stdout, stderr_snippet: stderr,
        file: absPath, file_hash_before: hashBefore
    });

    const filename = path.basename(absPath);
    const workingPath = path.join(WORKING_PATH, filename);
    const dest = status === 'COMPLETED_SUCCESS' ? path.join(FINAL_PATH, filename) : path.join(ERROR_PATH, filename);
    if (fs.existsSync(workingPath)) {
        try { fs.renameSync(workingPath, dest); } catch (e) { console.error(`[GOVERNOR] Move to final/error failed: ${e.message}`); }
    }
    executionRegistry.delete(lockPath);
}

// --- API ROUTES ---

app.get('/api/status', (req, res) => res.json({ status: 'READY', mode: EXECUTION_MODE, timestamp: new Date().toISOString() }));

app.get('/api/audit/:execution_id', (req, res) => {
    const entry = audit.getLatestEntryByExecutionId(LOG_PATH, req.params.execution_id);
    if (!entry) return res.status(404).json({ error_code: 'FILE_NOT_FOUND', message: 'ID not found' });
    const terminal = ['COMPLETED_SUCCESS', 'COMPLETED_FAILURE', 'TIMEOUT', 'RECOVERY'];
    res.json({ execution_id: req.params.execution_id, isTerminal: terminal.includes(entry.status), entry });
});

app.get('/api/files', (req, res) => {
    try {
        const files = fs.readdirSync(INBOX_PATH).filter(f => FILE_REGEX.test(f));
        res.json({ files });
    } catch (e) { res.status(500).json({ error_code: 'INTERNAL_FAILURE', message: 'Inbox error' }); }
});

const handleExecutionRequest = async (req, res, sourceDir) => {
    if (!checkRateLimit(req.ip)) return res.status(429).json({ error_code: 'RATE_LIMITED', message: 'Rate limit exceeded' });
    const { filename, confirm } = req.body;
    if (confirm !== true) return res.status(403).json({ error_code: 'GOVERNANCE_BLOCKED', message: 'Confirm required' });
    if (!filename || !FILE_REGEX.test(filename)) return res.status(400).json({ error_code: 'INVALID_RESOURCE', message: 'Invalid name' });

    const absPath = path.resolve(sourceDir, filename);
    if (!absPath.startsWith(sourceDir) || !fs.existsSync(absPath)) return res.status(404).json({ error_code: 'FILE_NOT_FOUND', message: 'File missing' });

    if (fs.statSync(absPath).size > MAX_FILE_SIZE_MB * 1024 * 1024) return res.status(400).json({ error_code: 'INVALID_RESOURCE', message: `File size exceeds ${MAX_FILE_SIZE_MB}MB limit` });

    // BLD-LIVE-003: CONCURRENCY LOCK BEFORE HASH/LOGGING
    if (executionRegistry.has(absPath)) return res.status(423).json({ error_code: 'RESOURCE_LOCKED', message: 'File is being processed' });

    const lastTime = lastActionTimes.get(absPath) || 0;
    if (Date.now() - lastTime < 5000) return res.status(429).json({ error_code: 'COOLDOWN_ACTIVE', message: 'Cooldown active (5s)' });

    const execution_id = uuidv4();
    executionRegistry.set(absPath, execution_id); // RESERVE LOCK
    lastActionTimes.set(absPath, Date.now());

    const hash = calculateFileHash(absPath);
    const startTime = Date.now();

    if (!hash) {
        executionRegistry.delete(absPath);
        return res.status(500).json({ error_code: 'INTERNAL_FAILURE', message: 'Hash calculation failed' });
    }

    // MANDATORY GOVERNANCE ORDER: Log STARTED BEFORE any FS mutation
    let startEntry;
    try {
        startEntry = audit.appendEntry(LOG_PATH, { execution_id, status: 'STARTED', mode: EXECUTION_MODE, timestamp: new Date().toISOString(), file: absPath, file_hash_before: hash });
    } catch (e) {
        executionRegistry.delete(absPath);
        return res.status(503).json({ error_code: 'INTEGRITY_VIOLATION', message: `Audit append failed: ${e.message}` });
    }

    if (EXECUTION_MODE === 'observe') {
        const completion = audit.appendEntry(LOG_PATH, { execution_id, status: 'COMPLETED_SUCCESS', mode: EXECUTION_MODE, timestamp: new Date().toISOString(), file: absPath, file_hash_before: hash, outcome: 'SIMULATED', runtime_ms: Date.now() - startTime });
        executionRegistry.delete(absPath);
        return res.status(202).json({ message: 'Authorized', execution_id, audit_entry: completion });
    }

    try {
        // SIDE EFFECTS START
        const stagingPath = path.join(STAGING_PATH, `${execution_id}.tmp`);
        fs.renameSync(absPath, stagingPath);
        const workingPath = path.join(WORKING_PATH, filename);
        fs.renameSync(stagingPath, workingPath);

        const child = spawn(PYTHON_PATH, [PIPELINE_RUNNER_PATH, '--file', workingPath], { shell: false, cwd: BASE_IDMS, env: { ...process.env, NODE_ENV: 'production' } });
        audit.appendEntry(LOG_PATH, { execution_id, status: 'EXECUTING', mode: EXECUTION_MODE, timestamp: new Date().toISOString(), file: absPath, file_hash_before: hash, pid: child.pid });

        let stdout = '', stderr = '';
        child.stdout.on('data', (d) => stdout += d.toString());
        child.stderr.on('data', (d) => stderr += d.toString());

        const timeout = setTimeout(() => {
            child.kill('SIGKILL');
            handleTerminalOutcome(execution_id, 'TIMEOUT', 'TIMEOUT', 'TIMEOUT', -1, PYTHON_TIMEOUT_MS, ['Timeout'], stdout, stderr, absPath, absPath, hash);
        }, PYTHON_TIMEOUT_MS);

        child.on('close', (code) => {
            clearTimeout(timeout);
            const runtime = Date.now() - startTime;
            if (code === 0) handleTerminalOutcome(execution_id, 'COMPLETED_SUCCESS', 'SUCCESS', 'NONE', 0, runtime, [], stdout, stderr, absPath, absPath, hash);
            else handleTerminalOutcome(execution_id, 'COMPLETED_FAILURE', 'FAILURE', 'RUNTIME_ERROR', code, runtime, [`Exit ${code}`], stdout, stderr, absPath, absPath, hash);
        });

        res.status(202).json({ message: 'Authorized', execution_id, audit_entry: startEntry });
    } catch (err) {
        handleTerminalOutcome(execution_id, 'COMPLETED_FAILURE', 'FAILURE', 'FILE_SYSTEM_ERROR', -1, Date.now() - startTime, [err.message], "", "", absPath, absPath, hash);
        res.status(500).json({ error_code: 'INTERNAL_FAILURE', message: `Filesystem error: ${err.message}`, execution_id, last_audit_entry: audit.getLatestEntryByExecutionId(LOG_PATH, execution_id) });
    }
};

app.post('/api/process', (req, res) => handleExecutionRequest(req, res, INBOX_PATH));
app.post('/api/finalize', (req, res) => handleExecutionRequest(req, res, REVIEW_PATH));
app.listen(PORT, () => console.log(`[GOVERNOR] Running on ${PORT}`));
