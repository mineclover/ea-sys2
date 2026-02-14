export interface IContractLoadOptions {
    contractDir?: string;
    validate?: boolean;
}
export interface IContractPaths {
    contractDir: string;
    schemaPath: string;
    rulesPath: string;
    vectorsPath: string;
}
export interface IKernelContractBundle {
    kernelVersion: string;
    paths: IContractPaths;
    schema: Record<string, unknown>;
    rules: Record<string, unknown>;
    vectors: Record<string, unknown>;
}
export interface IKernelContractSummary {
    available: boolean;
    contractDir: string | null;
    kernelVersion: string | null;
    entityCount: number;
    relationCount: number;
    totalRules: number;
    vectors: number;
    error?: string;
}
