
import { SimulationView } from '@/components/governance';
import { useAppState } from '@/contexts/AppStateContext';

export default function SimulationPage() {
    const { showDetail } = useAppState();
    return <SimulationView onShowDetail={showDetail} />;
}
