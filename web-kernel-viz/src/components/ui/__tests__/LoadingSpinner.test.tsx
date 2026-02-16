import { render, screen } from '@/test/test-utils';
import LoadingSpinner from '../LoadingSpinner';

describe('LoadingSpinner', () => {
    it('renders default loading message', () => {
        render(<LoadingSpinner />);
        expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('renders custom message', () => {
        render(<LoadingSpinner message="Fetching data..." />);
        expect(screen.getByText('Fetching data...')).toBeInTheDocument();
    });

    it('applies full-height styles by default', () => {
        render(<LoadingSpinner />);
        const el = screen.getByText('Loading...');
        expect(el).toHaveStyle({ flex: '1', height: '100%' });
    });

    it('omits full-height styles when fullHeight is false', () => {
        render(<LoadingSpinner fullHeight={false} />);
        const el = screen.getByText('Loading...');
        expect(el).not.toHaveStyle({ height: '100%' });
    });
});
