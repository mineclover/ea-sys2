import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { PAGE_META } from '@/config/pageMeta';

interface PageHeaderProps {
    metaKey: string;
    compact?: boolean;
    title?: string;
    subtitle?: string;
    rightContent?: ReactNode;
}

export default function PageHeader({ metaKey, compact, title, subtitle, rightContent }: PageHeaderProps) {
    const navigate = useNavigate();
    const meta = PAGE_META[metaKey];

    if (!meta) return null;

    const displayTitle = title ?? meta.title;

    return (
        <div style={{
            padding: compact ? '10px 16px' : '16px 20px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--secondary)',
        }}>
            {/* Row 1: Title + subtitle + rightContent */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
            }}>
                <span style={{
                    fontSize: compact ? 11 : 16,
                    fontWeight: 700,
                    color: compact ? 'var(--muted-foreground)' : 'var(--foreground)',
                    textTransform: compact ? 'uppercase' : undefined,
                }}>
                    {displayTitle}
                </span>
                {subtitle && (
                    <span style={{
                        fontSize: 12,
                        color: 'var(--muted-foreground)',
                    }}>
                        {subtitle}
                    </span>
                )}
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {rightContent}
                </div>
            </div>

            {/* Row 2+3: description, dataSources, relatedPages (hidden in compact) */}
            {!compact && (
                <>
                    <div style={{
                        fontSize: 12,
                        color: 'var(--muted-foreground)',
                        marginTop: 4,
                        lineHeight: 1.4,
                    }}>
                        {meta.description}
                    </div>
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 16,
                        marginTop: 8,
                        flexWrap: 'wrap',
                    }}>
                        {meta.dataSources.length > 0 && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>
                                    Data Sources
                                </span>
                                {meta.dataSources.map((src) => (
                                    <span key={src} style={{
                                        fontSize: 10,
                                        padding: '1px 6px',
                                        borderRadius: 3,
                                        background: 'var(--accent)',
                                        color: 'var(--muted-foreground)',
                                        fontWeight: 600,
                                    }}>
                                        {src}
                                    </span>
                                ))}
                            </div>
                        )}
                        {meta.relatedPages.length > 0 && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>
                                    Related
                                </span>
                                {meta.relatedPages.map((rp) => (
                                    <button
                                        key={rp.path}
                                        onClick={() => navigate(rp.path)}
                                        style={{
                                            fontSize: 10,
                                            padding: '1px 6px',
                                            borderRadius: 3,
                                            background: 'var(--muted)',
                                            color: 'var(--primary)',
                                            fontWeight: 600,
                                            border: 'none',
                                            cursor: 'pointer',
                                        }}
                                    >
                                        {rp.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
