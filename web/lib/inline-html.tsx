import { Fragment, type ReactNode, createElement } from "react";

/**
 * Render đoạn HTML inline đã được backend lọc whitelist.
 *
 * KHÔNG dùng dangerouslySetInnerHTML: ở đây HTML gốc đến từ site ngoài (vbpl.vn). Backend
 * đã bóc hết attribute và thẻ lạ, nhưng dựng React element từ một danh sách thẻ đóng cứng
 * là tuyến phòng thủ thứ hai — kể cả backend có lọt gì thì trình duyệt cũng không bao giờ
 * thấy thẻ đó, vì mọi thứ ngoài danh sách này được đối xử như chữ.
 */
const ALLOWED: Record<string, string> = {
  b: "strong",
  strong: "strong",
  i: "em",
  em: "em",
  u: "u",
  sup: "sup",
  sub: "sub",
};

const TOKEN = /<(\/?)([a-zA-Z]+)\s*\/?>/g;

function unescapeEntities(s: string): string {
  return s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&");
}

export function renderInline(html: string): ReactNode {
  if (!html) return null;
  // Mỗi phần tử stack là danh sách con đang gom cho một thẻ đang mở.
  const stack: { tag: string | null; children: ReactNode[] }[] = [
    { tag: null, children: [] },
  ];
  const push = (n: ReactNode) => stack[stack.length - 1].children.push(n);

  let last = 0;
  let key = 0;
  TOKEN.lastIndex = 0;
  for (let m = TOKEN.exec(html); m !== null; m = TOKEN.exec(html)) {
    const text = html.slice(last, m.index);
    if (text) push(unescapeEntities(text));
    last = m.index + m[0].length;

    const closing = m[1] === "/";
    const tag = m[2].toLowerCase();

    if (tag === "br") {
      if (!closing) push(<br key={key++} />);
      continue;
    }
    const mapped = ALLOWED[tag];
    if (!mapped) {
      // thẻ không nằm trong whitelist -> hiện nguyên văn như chữ, không diễn giải
      push(m[0]);
      continue;
    }
    if (!closing) {
      stack.push({ tag: mapped, children: [] });
    } else {
      // đóng nhầm thứ tự thì gộp hết về cha, không để mất chữ
      while (stack.length > 1) {
        const top = stack.pop()!;
        const el = createElement(top.tag!, { key: key++ }, ...top.children);
        stack[stack.length - 1].children.push(el);
        if (top.tag === mapped) break;
      }
    }
  }
  const tail = html.slice(last);
  if (tail) push(unescapeEntities(tail));

  // thẻ mở mà không đóng -> đóng nốt
  while (stack.length > 1) {
    const top = stack.pop()!;
    stack[stack.length - 1].children.push(
      createElement(top.tag!, { key: key++ }, ...top.children),
    );
  }
  return <Fragment>{stack[0].children}</Fragment>;
}
