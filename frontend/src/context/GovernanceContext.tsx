import React, { createContext, useContext, useState, ReactNode } from 'react';

type GovernanceMode = 'observe' | 'live';

interface GovernanceContextType {
    mode: GovernanceMode;
    isLive: boolean;
}

const GovernanceContext = createContext<GovernanceContextType | undefined>(undefined);

export const GovernanceProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const rawMode = import.meta.env.VITE_IDMS_EXECUTION_MODE;

    if (!rawMode) {
        throw new Error('FATAL: VITE_IDMS_EXECUTION_MODE is not defined in environment.');
    }

    const mode: GovernanceMode = rawMode === 'live' ? 'live' : 'observe';

    const value = {
        mode,
        isLive: mode === 'live',
    };

    return (
        <GovernanceContext.Provider value={value}>
            {children}
        </GovernanceContext.Provider>
    );
};

export const useGovernance = () => {
    const context = useContext(GovernanceContext);
    if (context === undefined) {
        throw new Error('useGovernance must be used within a GovernanceProvider');
    }
    return context;
};
