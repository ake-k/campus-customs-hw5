import { Fragment } from "react";

/** Agents sometimes answer in light markdown; render **bold** and drop stray list dashes. */
export function Rich({ text }: { text: string }) {
  const clean = text.replace(/^\s*[-*]\s+/gm, "• ");
  return (
    <>
      {clean.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? <b key={i}>{part.slice(2, -2)}</b> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}
