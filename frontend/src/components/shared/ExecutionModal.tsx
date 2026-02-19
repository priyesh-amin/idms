import React, { useState, useEffect } from 'react';
import styles from './ExecutionModal.module.css';
import GovernedButton from './GovernedButton';
import ModeBadge from './ModeBadge';
import { idmsClient, AuditManifest } from '../../api/idmsClient';
import { useGovernance } from '../../context/GovernanceContext';

interface ExecutionModalProps {
    isOpen: boolean;
    onClose: () => void;
    filename: string;
    actionType: 'authorize' | 'archive';
}

const ExecutionModal: React.FC<ExecutionModalProps> = ({
    isOpen,
    onClose,
    filename,
    actionType
}) => {
    const { mode } = useGovernance();
    const [isConfirmed, setIsConfirmed] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [manifest, setManifest] = useState<AuditManifest | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Reset state when opening/closing
    useEffect(() => {
        if (isOpen) {
            setIsConfirmed(false);
            setIsLoading(false);
            setManifest(null);
            setError(null);
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleConfirm = async () => {
        if (!isConfirmed) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = (actionType === 'authorize')
                ? await idmsClient.authorizeProcessing(filename, true)
                : await idmsClient.authorizeFinalize(filename, true);

            if (response.error) {
                setError(response.error);
            } else if (response.manifest) {
                setManifest(response.manifest);
            }
        } catch (err: any) {
            setError(err.message || 'System failure: Unable to communicate with Governance API');
        } finally {
            setIsLoading(false);
        }
    };

    const getTitle = () => {
        return actionType === 'authorize' ? 'Authorize Processing' : 'Authorize Archive';
    };

    const getDescription = () => {
        if (manifest) {
            return `Action authorized successfully in Observe Mode. The audit log has been updated with a SIMULATED status.`;
        }
        return `You are about to authorize ${actionType === 'authorize' ? 'processing' : 'archiving'} for "${filename}". This action will be logged in the immutable audit trail.`;
    };

    return (
        <div className={styles.overlay}>
            <div className={styles.modal}>
                {isLoading && (
                    <div className={styles.loadingOverlay}>
                        <div className={styles.spinner} />
                    </div>
                )}

                <div className={styles.header}>
                    <div className={styles.titleGroup}>
                        <h2>{getTitle()}</h2>
                        <ModeBadge mode={mode} />
                    </div>
                    <div className={styles.executionId}>
                        RESOURCE: <span>{filename}</span>
                    </div>
                </div>

                <div className={styles.body}>
                    <p>{getDescription()}</p>

                    {error && (
                        <div className={styles.errorBanner}>
                            <span>⚠️</span> {error}
                        </div>
                    )}

                    {!manifest && !error && (
                        <div className={styles.confirmGroup}>
                            <input
                                type="checkbox"
                                id="gov-confirm"
                                checked={isConfirmed}
                                onChange={(e) => setIsConfirmed(e.target.checked)}
                            />
                            <label htmlFor="gov-confirm">
                                I confirm this action as an authorized Governance Officer.
                            </label>
                        </div>
                    )}

                    {manifest && (
                        <div className={styles.manifest}>
                            <span className={styles.manifestTitle}>EXECUTION MANIFEST</span>
                            <div className={styles.manifestData}>
                                <div className={styles.property}>
                                    <span className={styles.label}>EXECUTION_ID:</span>
                                    <span className={styles.value}>{manifest.execution_id}</span>
                                </div>
                                <div className={styles.property}>
                                    <span className={styles.label}>HASH (BEFORE):</span>
                                    <span className={styles.value}>{manifest.file_hash_before.substring(0, 16)}...</span>
                                </div>
                                <div className={styles.property}>
                                    <span className={styles.label}>MODE:</span>
                                    <span className={styles.modeBadge}>{manifest.mode}</span>
                                </div>
                                <div className={styles.property}>
                                    <span className={styles.label}>STATUS:</span>
                                    <span className={`${styles.value} ${styles.statusSimulated}`}>SIMULATED</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <div className={styles.footer}>
                    {manifest ? (
                        <GovernedButton variant="primary" onClick={onClose}>
                            Close
                        </GovernedButton>
                    ) : (
                        <>
                            <GovernedButton variant="secondary" onClick={onClose} disabled={isLoading}>
                                Cancel
                            </GovernedButton>
                            <GovernedButton
                                variant="primary"
                                onClick={handleConfirm}
                                disabled={!isConfirmed || isLoading}
                            >
                                Authorize
                            </GovernedButton>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ExecutionModal;
