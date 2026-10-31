import { Fragment, type ReactNode } from "react";

/**
 * The chat model answers in Markdown (bold, bullet lists), and showing it raw
 * puts `**` in front of a carer. This renders the small subset the model uses —
 * paragraphs, line breaks, `-`/`*`/`1.` lists, `#` headings, bold, italic,
 * inline code — into React elements only. No HTML string is ever built, so
 * whatever the model writes stays text: no tags, links or images get through.
 *
 * `renderText` handles the plain-text runs (the chat links dates to the
 * calendar through it).
 */
export function renderChatMarkdown(text: string, renderText: (s: string) => ReactNode = (s) => s): ReactNode {
  const blocks: ReactNode[] = [];
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const bullet = /^\s*[-*•]\s+/;
    const ordered = /^\s*\d+[.)]\s+/;
    if (bullet.test(line) || ordered.test(line)) {
      const isOrdered = ordered.test(line) && !bullet.test(line);
      const re = isOrdered ? ordered : bullet;
      const items: string[] = [];
      while (i < lines.length && re.test(lines[i])) {
        let item = lines[i].replace(re, "");
        i++;
        // continuation lines: indented, not a new item, not blank
        while (i < lines.length && lines[i].trim() && /^\s{2,}/.test(lines[i]) && !bullet.test(lines[i]) && !ordered.test(lines[i])) {
          item += "\n" + lines[i].trim();
          i++;
        }
        items.push(item);
      }
      const ListTag = isOrdered ? "ol" : "ul";
      blocks.push(
        <ListTag key={blocks.length} className={`${isOrdered ? "list-decimal" : "list-disc"} space-y-1 pl-5`}>
          {items.map((it, k) => <li key={k}>{inline(it, renderText)}</li>)}
        </ListTag>,
      );
      continue;
    }

    const heading = /^\s*#{1,6}\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push(<p key={blocks.length} className="font-semibold">{inline(heading[1], renderText)}</p>);
      i++;
      continue;
    }

    // paragraph: consecutive lines until a blank line, list or heading
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !bullet.test(lines[i]) && !ordered.test(lines[i]) && !/^\s*#{1,6}\s/.test(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(<p key={blocks.length}>{inline(para.join("\n"), renderText)}</p>);
  }

  return <div className="space-y-2">{blocks}</div>;
}

// **bold** / __bold__, *italic* / _italic_ (not inside words), `code`
const INLINE_RE = /(\*\*|__)(?=\S)([\s\S]+?)(?<=\S)\1|(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])|(?<!\w)_(?=\S)([^_\n]+?)(?<=\S)_(?!\w)|`([^`\n]+)`/g;

function inline(text: string, renderText: (s: string) => ReactNode): ReactNode {
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(INLINE_RE)) {
    if (m.index > last) out.push(withBreaks(text.slice(last, m.index), renderText));
    if (m[2] !== undefined) out.push(<strong className="font-semibold">{inline(m[2], renderText)}</strong>);
    else if (m[3] !== undefined) out.push(<em>{inline(m[3], renderText)}</em>);
    else if (m[4] !== undefined) out.push(<em>{inline(m[4], renderText)}</em>);
    else out.push(<code className="rounded bg-background/60 px-1 font-mono text-[0.9em]">{m[5]}</code>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(withBreaks(text.slice(last), renderText));
  return out.map((n, k) => <Fragment key={k}>{n}</Fragment>);
}

function withBreaks(text: string, renderText: (s: string) => ReactNode): ReactNode {
  const parts = text.split("\n");
  return parts.map((p, k) => (
    <Fragment key={k}>
      {k > 0 && <br />}
      {renderText(p)}
    </Fragment>
  ));
}
