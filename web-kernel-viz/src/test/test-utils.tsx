import { type ReactElement } from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

function createTestQueryClient() {
    return new QueryClient({
        defaultOptions: {
            queries: {
                retry: false,
                gcTime: 0,
            },
        },
    });
}

interface WrapperOptions {
    route?: string;
}

function createWrapper(options: WrapperOptions = {}) {
    const { route = '/' } = options;
    const queryClient = createTestQueryClient();

    return function Wrapper({ children }: { children: React.ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                <MemoryRouter initialEntries={[route]}>
                    {children}
                </MemoryRouter>
            </QueryClientProvider>
        );
    };
}

function customRender(
    ui: ReactElement,
    options?: Omit<RenderOptions, 'wrapper'> & WrapperOptions,
) {
    const { route, ...renderOptions } = options ?? {};
    return render(ui, {
        wrapper: createWrapper({ route }),
        ...renderOptions,
    });
}

// Re-export everything from @testing-library/react
export * from '@testing-library/react';

// Override render with custom render
export { customRender as render };
