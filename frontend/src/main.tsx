import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { CssBaseline } from '@mui/material';
import { store } from './store';
import { WhiteLabelProvider } from './theme/WhiteLabelContext';
import App from './App';
import './index.css';

const root = document.getElementById('root');

if (!root) {
  throw new Error('Root element not found');
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <Provider store={store}>
      <WhiteLabelProvider>
        <CssBaseline />
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </WhiteLabelProvider>
    </Provider>
  </React.StrictMode>
);
