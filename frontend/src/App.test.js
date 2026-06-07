import { render, screen } from '@testing-library/react';
import App from './App';

test('renders SportsMD login', () => {
  render(<App />);
  expect(screen.getByText(/SportsMD/i)).toBeInTheDocument();
});
