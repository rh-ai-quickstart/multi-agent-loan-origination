import config from '@summit-cap/eslint-config';

export default [
    { ignores: ['dist/**', 'storybook-static/**', 'src/routeTree.gen.ts'] },
    ...config,
];
