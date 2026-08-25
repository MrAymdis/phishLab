/** markdown 渲染（AI 对话气泡统一入口）。
 * html: true —— 内部管理端，AI 输出经提示词约束且仅渲染可信气泡（演示数据含 <strong> 等）；
 * breaks: true —— 对话场景换行即换行，避免 LLM 单换行被折叠。
 */
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: true, linkify: true, breaks: true })

export function renderMarkdown(text: string): string {
  return md.render(text || '')
}
