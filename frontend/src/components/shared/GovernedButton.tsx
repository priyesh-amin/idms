import React from 'react';
import styles from './GovernedButton.module.css';

interface GovernedButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'danger';
    governanceAction?: 'authorize' | 'execute' | 'commit' | 'deauthorize';
}

const GovernedButton: React.FC<GovernedButtonProps> = ({
    children,
    variant = 'primary',
    governanceAction,
    className,
    ...props
}) => {
    const combinedClassName = `${styles.button} ${styles[variant]} ${className || ''}`;

    return (
        <button className={combinedClassName} {...props}>
            {children}
        </button>
    );
};

export default GovernedButton;
