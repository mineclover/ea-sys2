
import RulesView from '@/components/RulesView';
import { useAppState } from '@/contexts/AppStateContext';

export default function RulesPage() {
    const { showDetail } = useAppState();
    return <RulesView onShowDetail={showDetail} sidePanel={null} />;
}
