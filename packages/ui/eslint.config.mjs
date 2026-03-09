import config from '@mortgage-ai/eslint-config';

export default [
    { ignores: ['dist/**', 'storybook-static/**', 'src/routeTree.gen.ts'] },
    ...config,
];
