
import { ModelsView } from '@/components/governance';
import { useAppState } from '@/contexts/AppStateContext';

export default function ModelsPage() {
    const { showDetail } = useAppState();
    return <ModelsView onShowDetail={showDetail} />;
}
