import { Link } from "react-router-dom";
import { PageHeader } from "../ui.jsx";

export default function Copilot() {
  return (
    <>
      <PageHeader title="AI Copilot" sub="What the AI can do today" />
      <div className="grid2">
        <section className="card"><h2>Available now, inside Content Studio</h2>
          <p className="mu">Open any document and use the AI Copilot panel. Each action calls the AI provider through the server.</p>
          {["Rewrite in a chosen tone", "Improve clarity and grammar", "Headline and call-to-action ideas", "Brand voice check", "Repurpose a post as a LinkedIn post, an email or a social caption"].map((t) => <div className="li" key={t}><span>{t}</span></div>)}
          <p className="small mu">Rewrites become a new version and never change the old one. Suggestions are not saved. The AI never publishes anything.</p>
          <Link className="btn primary" to="/content">Open Content Studio</Link></section>
        <section className="card"><h2>Not built yet</h2>
          <p className="mu">A chat assistant that can call tools (for example "create a campaign for Eid") is planned. It will recommend first, ask for confirmation before any external action, and record every tool call in the audit log.</p>
          <p className="small mu">Until then, nothing on this page pretends to be a chat.</p></section>
      </div>
    </>
  );
}
