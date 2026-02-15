
import { NeedsCatalogView } from '@/components/needs';
import { useAppState } from '@/contexts/AppStateContext';

export default function NeedsCatalogPage() {
    const { showDetail } = useAppState();
    return <NeedsCatalogView onShowDetail={showDetail} />;
}
