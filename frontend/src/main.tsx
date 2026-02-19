import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/index.css';
import { GovernanceProvider } from './context/GovernanceContext';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <GovernanceProvider>
      <App />
    </GovernanceProvider>
  </React.StrictMode>
);
