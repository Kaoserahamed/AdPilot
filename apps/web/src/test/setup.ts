import * as matchers from '@testing-library/jest-dom/matchers';
import { cleanup } from '@testing-library/react';
import { afterEach, expect } from 'vitest';

// The standalone `matchers` entry point is used instead of `@testing-library/jest-dom/vitest`
// because the latter imports `vitest` itself, which cannot resolve across npm workspace
// hoisting boundaries. Extending `expect` directly has the same effect without that edge.
expect.extend(matchers);

// Each test owns its own DOM subtree. Without this, rendered nodes leak between
// test files and `screen.getByRole` starts matching elements from a prior test.
afterEach(() => {
  cleanup();
});