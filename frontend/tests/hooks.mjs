export async function resolve(specifier, context, nextResolve) {
  if (specifier === "next/server") {
    return nextResolve("next/server.js", context);
  }
  if (specifier.startsWith("@/")) {
    const subpath = specifier.slice(2);
    const resolvedPath = new URL(`../src/${subpath}${subpath.endsWith(".ts") ? "" : ".ts"}`, import.meta.url).href;
    return nextResolve(resolvedPath, context);
  }
  return nextResolve(specifier, context);
}
