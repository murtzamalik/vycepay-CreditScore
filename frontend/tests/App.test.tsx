import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { store } from '../src/store';
import theme from '../src/theme';
import App from '../src/App';

function renderApp(initialRoute = '/login') {
  return render(
    <Provider store={store}>
      <ThemeProvider theme={theme}>
        <MemoryRouter initialEntries={[initialRoute]}>
          <App />
        </MemoryRouter>
      </ThemeProvider>
    </Provider>
  );
}

describe('App', () => {
  it('renders the login page at /login', () => {
    renderApp('/login');
    expect(screen.getByText('VyceScore')).toBeDefined();
    expect(screen.getByText('Sign In')).toBeDefined();
  });

  it('renders without crashing', () => {
    const { container } = renderApp();
    expect(container).toBeDefined();
  });
});
