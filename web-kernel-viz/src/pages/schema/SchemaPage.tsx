
import { useParams } from 'react-router-dom';
import { LayerStackView } from '@/components/schema';
import { useAppState } from '@/contexts/AppStateContext';

export default function SchemaPage() {
    const { layerKey } = useParams<{ layerKey: string }>();
    const { lang } = useAppState();
    return <LayerStackView layerKey={layerKey || 'kernel'} lang={lang} />;
}
