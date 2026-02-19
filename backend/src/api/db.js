const { Pool } = require('pg');

let pool;

function connectionConfig() {
  if (process.env.IDMS_PG_DSN) {
    return {
      connectionString: process.env.IDMS_PG_DSN,
      max: parseInt(process.env.IDMS_DB_POOL_MAX || '10', 10),
      idleTimeoutMillis: parseInt(process.env.IDMS_DB_IDLE_TIMEOUT_MS || '30000', 10),
    };
  }

  return {
    host: process.env.IDMS_PG_HOST || '127.0.0.1',
    port: parseInt(process.env.IDMS_PG_PORT || '5432', 10),
    database: process.env.IDMS_PG_DB || 'idms',
    user: process.env.IDMS_PG_USER || 'idms',
    password: process.env.IDMS_PG_PASSWORD || 'idms',
    max: parseInt(process.env.IDMS_DB_POOL_MAX || '10', 10),
    idleTimeoutMillis: parseInt(process.env.IDMS_DB_IDLE_TIMEOUT_MS || '30000', 10),
  };
}

function getPool() {
  if (!pool) {
    pool = new Pool(connectionConfig());
    pool.on('error', (err) => {
      console.error('[DB] Unexpected idle client error:', err.message);
    });
  }
  return pool;
}

async function query(text, params = []) {
  return getPool().query(text, params);
}

async function healthCheck() {
  try {
    await query('SELECT 1 AS ok');
    return true;
  } catch {
    return false;
  }
}

module.exports = {
  getPool,
  query,
  healthCheck,
};
