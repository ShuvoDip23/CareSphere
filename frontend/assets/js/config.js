/* Runtime configuration.
 *
 * The old frontend hard-coded http://127.0.0.1:5000 in three separate files,
 * which made the app impossible to deploy. Override at build/deploy time by
 * setting window.__CARESPHERE_API__ before this script loads, or via a
 * <meta name="caresphere-api" content="..."> tag.
 */

const metaOrigin = document.querySelector('meta[name="caresphere-api"]')?.getAttribute("content");

export const API_ORIGIN = window.__CARESPHERE_API__ || metaOrigin || "http://127.0.0.1:5000";

export const API_BASE_URL = `${API_ORIGIN}/api`;
