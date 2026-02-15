
import { DecisionsView } from '@/components/governance';
import { useAppState } from '@/contexts/AppStateContext';

export default function DecisionsPage() {
    const { showDetail } = useAppState();
    return <DecisionsView onShowDetail={showDetail} />;
}
