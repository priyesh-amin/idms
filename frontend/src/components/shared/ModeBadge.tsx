import React from 'react';
import styles from './ModeBadge.module.css';

interface ModeBadgeProps {
    mode: 'observe' | 'live';
}

const ModeBadge: React.FC<ModeBadgeProps> = ({ mode }) => {
    const isLive = mode === 'live';
    return (
        <div className={`${styles.badge} ${isLive ? styles.live : styles.observe}`}>
            <span className={styles.dot}></span>
            {mode.toUpperCase()}
        </div>
    );
};

export default ModeBadge;
