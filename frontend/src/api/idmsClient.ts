/**
 * BLD-005: IDMS API Client
 * 
 * Hardened fetch wrapper for IDMS Backend.
 * Enforces strict environment checks and schema alignment.
 */

if (!import.meta.env.VITE_IDMS_API_BASE_URL) {
    throw new Error("VITE_IDMS_API_BASE_URL not defined");
}

const API_BASE_URL = import.meta.env.VITE_IDMS_API_BASE_URL;

export interface AuditManifest {
    execution_id: string;
    status: string;
    mode: string;
    timestamp: string;
    file: string;
    file_hash_before: string;
    outcome: string;
    runtime_ms: number;
    errors: string[];
    previous_entry_hash: string;
    entry_hash: string;
}

export interface ApiResponse<T> {
    message?: string;
    manifest?: T;
    execution_id?: string;
    error?: string;
    files?: string[];
    status?: string;
    mode?: string;
}

const handleResponse = async <T>(res: Response): Promise<ApiResponse<T>> => {
    if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || `HTTP Error ${res.status}`);
    }
    return res.json();
};

export const idmsClient = {
    async getStatus(): Promise<ApiResponse<never>> {
        const res = await fetch(`${API_BASE_URL}/api/status`);
        return handleResponse<never>(res);
    },

    async getFiles(): Promise<{ files: string[] }> {
        const res = await fetch(`${API_BASE_URL}/api/files`);
        if (!res.ok) throw new Error('Failed to fetch files');
        return res.json();
    },

    async authorizeProcessing(filename: string, confirm: boolean): Promise<ApiResponse<AuditManifest>> {
        const res = await fetch(`${API_BASE_URL}/api/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, confirm })
        });
        return handleResponse<AuditManifest>(res);
    },

    async authorizeFinalize(filename: string, confirm: boolean): Promise<ApiResponse<AuditManifest>> {
        const res = await fetch(`${API_BASE_URL}/api/finalize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, confirm })
        });
        return handleResponse<AuditManifest>(res);
    }
};
