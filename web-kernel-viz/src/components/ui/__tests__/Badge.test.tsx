import { render, screen } from '@/test/test-utils';
import Badge from '../Badge';

describe('Badge', () => {
    it('renders with the given label', () => {
        render(<Badge label="ACTIVE" />);
        expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    it('applies preset colors for known labels', () => {
        render(<Badge label="APPROVED" />);
        const badge = screen.getByText('APPROVED');
        expect(badge).toHaveStyle({ background: 'var(--success-bg)', color: 'var(--success-text)' });
    });

    it('falls back to default colors for unknown labels', () => {
        render(<Badge label="custom-label" />);
        const badge = screen.getByText('custom-label');
        expect(badge).toHaveStyle({ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' });
    });

    it('uses custom color and bg when provided', () => {
        render(<Badge label="TEST" color="#ff0000" bg="#00ff00" />);
        const badge = screen.getByText('TEST');
        expect(badge).toHaveStyle({ background: '#00ff00', color: '#ff0000' });
    });

    it('supports md size variant', () => {
        render(<Badge label="MEDIUM" size="md" />);
        const badge = screen.getByText('MEDIUM');
        expect(badge).toHaveStyle({ fontSize: '11px', padding: '3px 8px' });
    });
});
