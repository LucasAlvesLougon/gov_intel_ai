import { Suspense } from "react";
import { ChatView } from "../../components/chat-view";

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="search-status">Carregando…</div>}>
      <ChatView />
    </Suspense>
  );
}
