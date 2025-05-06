export function changeTextToHTML(text: string) {
  return text.replace(/\n/g, '<br>').trim();
}

export function changeHTMLToText(html: string) {
  return html.replace(/<br\s*\/?>/gi, '\n').trim();
}
