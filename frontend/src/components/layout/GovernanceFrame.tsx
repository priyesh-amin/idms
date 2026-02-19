import React from 'react';
import { useGovernance } from '../../context/GovernanceContext';
import styles from './GovernanceFrame.module.css';

interface GovernanceFrameProps {
    children: React.ReactNode;
}

const GovernanceFrame: React.FC<GovernanceFrameProps> = ({ children }) => {
    const { mode, isLive } = useGovernance();

    return (
        <div className={`${styles.root} ${isLive ? styles.live : styles.observe}`}>
            <header className={styles.header}>
                <div className={styles.brand}>
                    <span className={styles.logo}>A</span>
                    <span className={styles.companyName}>AGILE BUSINESS CONSULTANCY</span>
                </div>
                <div className={styles.modeContainer}>
                    <div className={`${styles.modeIndicator} ${isLive ? styles.liveIndicator : styles.observeIndicator}`}>
                        {mode.toUpperCase()} MODE
                    </div>
                </div>
            </header>
            <main className={styles.content}>
                {children}
            </main>
            <footer className={styles.footer}>
                <div className={styles.governanceNote}>
                    Governed by IDMS-V6-GOV • Standardizing Reputation into Revenue
                </div>
            </footer>
        </div>
    );
};

export default GovernanceFrame;
