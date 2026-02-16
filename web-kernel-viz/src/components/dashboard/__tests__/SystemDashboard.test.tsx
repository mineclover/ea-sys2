import { render, screen, waitFor } from '@/test/test-utils';
import SystemDashboard from '../SystemDashboard';

describe('SystemDashboard', () => {
    it('shows loading state initially', () => {
        render(<SystemDashboard />);
        expect(screen.getByText('Loading dashboard...')).toBeInTheDocument();
    });

    it('renders dashboard content after data loads', async () => {
        render(<SystemDashboard />);

        await waitFor(() => {
            expect(screen.getByText('System Overview')).toBeInTheDocument();
        });

        // Verify schema stats are rendered
        expect(screen.getByText('Kernel Schema')).toBeInTheDocument();
        expect(screen.getByText('15 entities')).toBeInTheDocument();
        expect(screen.getByText('6 relations')).toBeInTheDocument();

        // Verify layer cards are rendered
        expect(screen.getByText('Kernel')).toBeInTheDocument();
        expect(screen.getByText('Flow')).toBeInTheDocument();

        // Verify framework badge is rendered
        expect(screen.getByText('TOGAF 10.0')).toBeInTheDocument();
    });

    it('renders cross-layer topology stats', async () => {
        render(<SystemDashboard />);

        await waitFor(() => {
            expect(screen.getByText('Cross-Layer Topology')).toBeInTheDocument();
        });

        expect(screen.getByText('12 nodes')).toBeInTheDocument();
        expect(screen.getByText('18 edges')).toBeInTheDocument();
    });

    it('renders needs catalogs section', async () => {
        render(<SystemDashboard />);

        await waitFor(() => {
            expect(screen.getByText('Needs Catalogs')).toBeInTheDocument();
        });

        expect(screen.getByText('5 needs total')).toBeInTheDocument();
    });
});
