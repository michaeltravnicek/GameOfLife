// The only two things the app needs from @sentry/react, re-exported so that
// services/sentry.js can `import('./sentrySdk')` lazily. Named imports here
// let the bundler tree-shake the SDK to what `init` actually needs; a dynamic
// `import('@sentry/react')` of the package itself would keep every export
// alive (tracing, replay, feedback, …) and ship five times the bytes.
export { init, captureException } from '@sentry/react';
