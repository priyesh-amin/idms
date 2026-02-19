const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

/**
 * ARC-006: Audit Integrity Helper
 * 
 * Enforces Deterministic Canonicalization and Schema Consistency.
 */

const KEY_ORDER = [
    'execution_id',
    'status',
    'mode',
    'timestamp',
    'file',
    'file_hash_before',
    'outcome',
    'pid',
    'exit_code',
    'failure_category',
    'stdout_snippet',
    'stderr_snippet',
    'runtime_ms',
    'errors',
    'previous_entry_hash'
];

const DEFAULTS = {
    execution_id: "",
    status: "",
    mode: "observe",
    timestamp: "",
    file: "",
    file_hash_before: "",
    outcome: "NONE",
    pid: 0,
    exit_code: -1,
    failure_category: "NONE",
    stdout_snippet: "",
    stderr_snippet: "",
    runtime_ms: 0,
    errors: [],
    previous_entry_hash: "GENESIS"
};

/**
 * Truncates string to max bytes for UTF-8 encoding.
 */
function truncateSnippet(str, maxBytes = 4096) {
    if (!str) return "";
    let buf = Buffer.from(str, 'utf8');
    if (buf.length <= maxBytes) return str;

    // Truncate and add suffix
    const suffix = "…TRUNCATED";
    const suffixBuf = Buffer.from(suffix, 'utf8');
    const truncatedBuf = buf.slice(0, maxBytes - suffixBuf.length);
    return truncatedBuf.toString('utf8') + suffix;
}

/**
 * [ARC-006] Fixed Schema Output
 * Always outputs all keys in KEY_ORDER with defaults.
 */
function canonicalize(obj) {
    const ordered = {};
    KEY_ORDER.forEach(key => {
        const val = obj[key];
        const defaultVal = DEFAULTS[key];

        if (val !== undefined && val !== null) {
            // Apply truncation if it's a snippet field
            if (key === 'stdout_snippet' || key === 'stderr_snippet') {
                ordered[key] = truncateSnippet(String(val));
            }
            // Type consistency
            else if (Array.isArray(defaultVal)) {
                ordered[key] = Array.isArray(val) ? val : [val];
            } else if (typeof defaultVal === 'number') {
                ordered[key] = typeof val === 'number' ? val : (Number(val) || 0);
            } else {
                ordered[key] = String(val);
            }
        } else {
            ordered[key] = defaultVal;
        }
    });
    return JSON.stringify(ordered);
}

function calculateHash(previousHash, entryWithoutHash) {
    const entryCopy = { ...entryWithoutHash, previous_entry_hash: previousHash };
    const canonical = canonicalize(entryCopy);
    return crypto.createHash('sha256').update(canonical).digest('hex');
}

/**
 * [ARC-006] Robust entry retrieval
 */
function getLastEntry(logPath) {
    if (!fs.existsSync(logPath)) return null;
    const lines = fs.readFileSync(logPath, 'utf8').split('\n').filter(l => l.trim());
    if (lines.length === 0) return null;
    try {
        return JSON.parse(lines[lines.length - 1]);
    } catch (e) {
        return null;
    }
}

function getEntriesByExecutionId(logPath, execution_id) {
    if (!fs.existsSync(logPath)) return [];
    try {
        const lines = fs.readFileSync(logPath, 'utf8').split('\n').filter(l => l.trim());
        return lines
            .map(l => JSON.parse(l))
            .filter(e => e.execution_id === execution_id);
    } catch (e) {
        return [];
    }
}

function getLatestEntryByExecutionId(logPath, execution_id) {
    const entries = getEntriesByExecutionId(logPath, execution_id);
    return entries.length > 0 ? entries[entries.length - 1] : null;
}

/**
 * [ARC-006] Validates integrity of the entire chain
 */
function verifyChain(logPath) {
    if (!fs.existsSync(logPath)) return true;
    const lines = fs.readFileSync(logPath, 'utf8').split('\n').filter(l => l.trim());

    let expectedPrevHash = 'GENESIS';

    for (let i = 0; i < lines.length; i++) {
        const fullEntry = JSON.parse(lines[i]);
        const { entry_hash, ...rest } = fullEntry;

        if (fullEntry.previous_entry_hash !== expectedPrevHash) {
            throw new Error(`Integrity Violation: Chain broken at line ${i + 1}.`);
        }

        const calculated = calculateHash(expectedPrevHash, rest);
        if (calculated !== entry_hash) {
            throw new Error(`Integrity Violation: Hash mismatch at line ${i + 1}.`);
        }

        expectedPrevHash = entry_hash;
    }
    return true;
}

/**
 * [ARC-006] Appends entry with forced schema and stripped caller hashes
 */
function appendEntry(logPath, entry) {
    const { previous_entry_hash: _p, entry_hash: _e, ...cleanEntry } = entry;

    const lastEntry = getLastEntry(logPath);
    const previous_entry_hash = lastEntry ? lastEntry.entry_hash : 'GENESIS';

    const entry_hash = calculateHash(previous_entry_hash, cleanEntry);

    // Final canonical object (keys in order)
    const finalObject = JSON.parse(canonicalize({ ...cleanEntry, previous_entry_hash }));
    finalObject.entry_hash = entry_hash;

    fs.appendFileSync(logPath, JSON.stringify(finalObject) + '\n');
    return finalObject;
}

/**
 * [ARC-006] Scans for orphans and injects RECOVERY entries
 */
function recoverOrphans(logPath, mode) {
    if (!fs.existsSync(logPath)) return;
    const lines = fs.readFileSync(logPath, 'utf8').split('\n').filter(l => l.trim());

    const terminalStatuses = ['COMPLETED_SUCCESS', 'COMPLETED_FAILURE', 'TIMEOUT', 'RECOVERY'];
    const activeExecutions = new Map();

    lines.forEach(line => {
        try {
            const entry = JSON.parse(line);
            if (terminalStatuses.includes(entry.status)) {
                activeExecutions.delete(entry.execution_id);
            } else if (entry.status === 'STARTED' || entry.status === 'EXECUTING') {
                activeExecutions.set(entry.execution_id, entry);
            }
        } catch (e) { }
    });

    activeExecutions.forEach((entry, id) => {
        appendEntry(logPath, {
            execution_id: id,
            status: 'RECOVERY',
            mode: mode,
            timestamp: new Date().toISOString(),
            file: entry.file,
            file_hash_before: entry.file_hash_before,
            outcome: 'INTERRUPTED',
            failure_category: 'SYSTEM_RECOVERY',
            errors: ['Server restarted before completion']
        });
        console.log(`[GOVERNOR] Recovered orphan: ${id}`);
    });
}

module.exports = {
    verifyChain,
    appendEntry,
    recoverOrphans,
    getLatestEntryByExecutionId,
    getEntriesByExecutionId
};
