
import { NeedsCatalogView } from '@/components/needs';
import { useAppState } from '@/contexts/AppStateContext';

export default function NeedsCatalogPage() {
    const { showDetail, lang } = useAppState();
    return <NeedsCatalogView onShowDetail={showDetail} lang={lang} />;
}
