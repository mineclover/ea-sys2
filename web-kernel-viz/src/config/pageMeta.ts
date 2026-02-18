export interface PageMeta {
    title: string;
    description: string;
    dataSources: string[];
    relatedPages: { label: string; path: string }[];
}

export const PAGE_META: Record<string, PageMeta> = {
    dashboard: {
        title: 'System Overview',
        description: 'EA-Sys Governance Framework dashboard showing layer profiles, governance activity, and framework coverage.',
        dataSources: ['governance/dashboard', 'cross-layer/summary', 'needs/catalogs'],
        relatedPages: [
            { label: 'Layers', path: '/status/layers' },
            { label: 'Rule Lifecycle', path: '/governance/rule-lifecycle' },
            { label: 'Needs Catalog', path: '/needs/catalog' },
        ],
    },
    'governance.rule-lifecycle': {
        title: 'Rule Lifecycle',
        description: 'Manage governance rules through their lifecycle: draft, submitted, approved, active, deprecated.',
        dataSources: ['governance/rules'],
        relatedPages: [
            { label: 'Simulation', path: '/governance/simulation' },
            { label: 'Models', path: '/governance/models' },
            { label: 'Decisions', path: '/governance/decisions' },
        ],
    },
    'governance.models': {
        title: 'Governance Models',
        description: 'Register, validate, and activate governance models. Manage model lifecycle and versioning.',
        dataSources: ['governance/models'],
        relatedPages: [
            { label: 'Rule Lifecycle', path: '/governance/rule-lifecycle' },
            { label: 'Simulation', path: '/governance/simulation' },
        ],
    },
    'governance.decisions': {
        title: 'Decision Explorer',
        description: 'Trace and explore governance decisions. View evidence, conflicts, and decision graphs.',
        dataSources: ['governance/decisions'],
        relatedPages: [
            { label: 'Simulation', path: '/governance/simulation' },
            { label: 'Impact Analysis', path: '/governance/impact' },
            { label: 'Rules', path: '/explorer/rules' },
        ],
    },
    'governance.simulation': {
        title: 'What-If Simulation',
        description: 'Simulate the impact of promoting a rule to a new confidence level. Shows affected decisions, verdict changes, and risk assessment.',
        dataSources: ['governance/simulation', 'kernel/rules'],
        relatedPages: [
            { label: 'Rule Lifecycle', path: '/governance/rule-lifecycle' },
            { label: 'Impact Analysis', path: '/governance/impact' },
            { label: 'Decisions', path: '/governance/decisions' },
        ],
    },
    'governance.impact': {
        title: 'Impact Analysis',
        description: 'Analyze the impact of changing a profile element. Shows upstream and downstream affected elements with propagation paths.',
        dataSources: ['governance/impact', 'profiles'],
        relatedPages: [
            { label: 'Simulation', path: '/governance/simulation' },
            { label: 'Entities', path: '/status/entities' },
            { label: 'Relations', path: '/status/relations' },
        ],
    },
    'needs.catalog': {
        title: 'Needs Catalogs',
        description: 'Browse and manage stakeholder needs, priorities, and kernel references across catalogs.',
        dataSources: ['needs/catalogs'],
        relatedPages: [
            { label: 'Dashboard', path: '/' },
            { label: 'Entities', path: '/status/entities' },
        ],
    },
    'status.entities': {
        title: 'Elements',
        description: 'Browse all profile elements grouped by profile and layer.',
        dataSources: ['profiles', 'topology'],
        relatedPages: [
            { label: 'Relations', path: '/status/relations' },
            { label: 'Rules', path: '/status/rules' },
            { label: 'Kernel Schema', path: '/status/kernel' },
        ],
    },
    'status.relations': {
        title: 'Relations',
        description: 'Browse all profile relations grouped by profile and relation type.',
        dataSources: ['profiles', 'topology'],
        relatedPages: [
            { label: 'Entities', path: '/status/entities' },
            { label: 'Rules', path: '/status/rules' },
            { label: 'Kernel Schema', path: '/status/kernel' },
        ],
    },
    'status.rules': {
        title: 'Kernel Rules',
        description: 'Overview of kernel rules by group with explicit/fallback breakdown.',
        dataSources: ['kernel/rules'],
        relatedPages: [
            { label: 'Entities', path: '/status/entities' },
            { label: 'Relations', path: '/status/relations' },
            { label: 'Explorer Rules', path: '/explorer/rules' },
        ],
    },
    'status.layers': {
        title: 'Layer Comparison',
        description: 'Compare element, relation, rule, node, and edge counts across all layers.',
        dataSources: ['cross-layer/summary', 'governance/dashboard'],
        relatedPages: [
            { label: 'Entities', path: '/status/entities' },
            { label: 'Frameworks', path: '/status/frameworks' },
            { label: 'Dashboard', path: '/' },
        ],
    },
    'status.frameworks': {
        title: 'Frameworks',
        description: 'Registered frameworks with entity, relation, and rule counts.',
        dataSources: ['governance/dashboard'],
        relatedPages: [
            { label: 'Layers', path: '/status/layers' },
            { label: 'Kernel Schema', path: '/status/kernel' },
        ],
    },
    'status.kernel': {
        title: 'Kernel Metamodel Schema',
        description: 'Entity types, relation types, and rules defined in the kernel metamodel.',
        dataSources: ['kernel/entities', 'kernel/relations', 'kernel/rules'],
        relatedPages: [
            { label: 'Entities', path: '/status/entities' },
            { label: 'Relations', path: '/status/relations' },
            { label: 'Rules', path: '/status/rules' },
        ],
    },
    'explorer.rules': {
        title: 'Rule Explorer',
        description: 'Browse kernel rules by group and execute judge queries to evaluate source-target-relation triples.',
        dataSources: ['kernel/rules', 'kernel/judge'],
        relatedPages: [
            { label: 'Kernel Rules', path: '/status/rules' },
            { label: 'Decisions', path: '/governance/decisions' },
            { label: 'Simulation', path: '/governance/simulation' },
        ],
    },
    'explorer.dev-topology': {
        title: 'Dev Topology',
        description: 'Development system topology graph for EASystem-Development profile.',
        dataSources: ['profiles/EASystem-Development/topology'],
        relatedPages: [
            { label: 'Entities', path: '/status/entities' },
            { label: 'Layers', path: '/status/layers' },
        ],
    },
    'admin.business': {
        title: 'Business Models',
        description: 'Create and manage business models with tag schemas, fields, and indexes.',
        dataSources: ['business/models', 'business/tags'],
        relatedPages: [
            { label: 'Business Flow', path: '/governance/business-flow' },
            { label: 'Dashboard', path: '/' },
        ],
    },
    'admin.i18n': {
        title: 'Translation Manager',
        description: 'Manage i18n translations, audit coverage, and resolve missing/orphan/stale entries.',
        dataSources: ['i18n/audit', 'i18n/translations'],
        relatedPages: [
            { label: 'Entities', path: '/status/entities' },
            { label: 'Kernel Schema', path: '/status/kernel' },
        ],
    },
    'admin.self-model': {
        title: 'System Self-Model',
        description: 'Mermaid diagram representing the system\'s self-model.',
        dataSources: ['system/self-model'],
        relatedPages: [
            { label: 'Dashboard', path: '/' },
            { label: 'Layers', path: '/status/layers' },
        ],
    },
};
