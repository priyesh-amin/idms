import React, { useState, useEffect } from 'react';
import GovernanceFrame from './components/layout/GovernanceFrame';
import ModeBadge from './components/shared/ModeBadge';
import GovernedButton from './components/shared/GovernedButton';
import GovernedTable from './components/shared/GovernedTable';
import { useGovernance } from './context/GovernanceContext';
import { idmsClient } from './api/idmsClient';
import styles from './App.module.css';

const App: React.FC = () => {
  const { mode } = useGovernance();
  const [files, setFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const res = await idmsClient.getFiles();
        setFiles(res.files);
        if (res.files.length > 0) {
          setSelectedFile(res.files[0]);
        }
      } catch (err) {
        console.error("FAILED_TO_FETCH_FILES", err);
      }
    };
    fetchFiles();
  }, []);

  const handleAuthorize = async () => {
    if (!selectedFile) return;

    console.log("AUTHORIZE_CLICK_TRIGGERED");
    setLoading(true);

    try {
      const response = await idmsClient.authorizeProcessing(selectedFile, true);
      console.log("API_RESPONSE_RECEIVED", response);
      alert(`Authorization Success: ${response.execution_id || 'OK'}`);
    } catch (err) {
      console.error("API_ERROR", err);
      alert(`Authorization Failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { header: 'Filename', accessor: (f: string) => f },
    {
      header: 'Status',
      accessor: (f: string) => (f === selectedFile ? 'SELECTED' : 'READY')
    }
  ];

  return (
    <GovernanceFrame>
      <section className={styles.container}>
        <header className={styles.header}>
          <div className={styles.titleGroup}>
            <h1>IDMS Dashboard</h1>
            <p className={styles.description}>Identity & Document Management System</p>
          </div>
          <div className={styles.controls}>
            <ModeBadge mode={mode} />
          </div>
        </header>

        <div className={styles.skeletonHint}>
          PHASE A SKELETON ACTIVE - STANDING BY FOR MODULE INJECTION
        </div>

        <div className={styles.content}>
          <GovernedTable
            data={files}
            columns={columns}
            rowKey={(f: string) => f as any}
            onRowClick={(f: string) => setSelectedFile(f)}
          />
        </div>

        <div className={styles.actions}>
          <GovernedButton
            variant="primary"
            onClick={handleAuthorize}
            disabled={!selectedFile || loading}
          >
            {loading ? 'Authorizing...' : 'Authorize Processing'}
          </GovernedButton>
          <GovernedButton variant="secondary" disabled>Commit Metadata</GovernedButton>
          <GovernedButton variant="danger" disabled>Deauthorize Resource</GovernedButton>
        </div>
      </section>
    </GovernanceFrame>
  );
};

export default App;
