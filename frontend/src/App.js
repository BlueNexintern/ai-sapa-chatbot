import React, { useEffect, useMemo, useRef, useState } from "react";
import { Send, Bot, User, Loader2, History, Search, X } from "lucide-react";
import { motion } from "framer-motion";
import "./App.css"; // ← CSS 분리

export default function App() {
  const [messages, setMessages] = useState([
    { id: crypto.randomUUID(), role: "assistant", text: "안녕하세요! 가짜 AI 챗봇 더미입니다. 무엇을 도와드릴까요?" },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [theme, setTheme] = useState("light"); // light | dark
  const [history, setHistory] = useState([]); // 최근 질문(최대 10)

  // 🔎 검색 상태
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [results, setResults] = useState([]); // {id, role, text, indices: [start,end]}

  const listRef = useRef(null);
  const msgRefs = useRef(new Map()); // id -> HTMLElement

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isLoading]);

  const placeholder = useMemo(
    () => (isLoading ? "응답 생성 중…" : "메시지를 입력하세요 (Enter=전송, Shift+Enter=줄바꿈)"),
    [isLoading]
  );

  function streamFake(text, speed = 12) {
    return new Promise((resolve) => {
      let i = 0;
      const id = crypto.randomUUID();
      setMessages((prev) => [...prev, { id, role: "assistant", text: "" }]);
      const interval = setInterval(() => {
        i += 1;
        setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, text: text.slice(0, i) } : m)));
        if (i >= text.length) {
          clearInterval(interval);
          resolve();
        }
      }, speed);
    });
  }

  async function onSubmit(e) {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg = { id: crypto.randomUUID(), role: "user", text: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setHistory((prev) => [userMsg.text, ...prev.slice(0, 9)]);
    setInput("");
    setIsLoading(true);

    const lower = userMsg.text.toLowerCase();
    let reply = "좋은 질문이에요! 하지만 저는 더미에요. 진짜 모델을 연결하면 훨씬 똑똑해져요.";

    if (/(hello|hi|안녕)/.test(lower)) reply = "안녕하세요! 무엇을 만들어볼까요?";
    else if (/help|도움|사용법/.test(lower)) reply = "아래 입력창에 질문을 쓰고 Enter를 누르세요. 나중에 /api/chat을 실제 백엔드로 연결하면 됩니다.";
    else if (/api|연결|백엔드|서버/.test(lower)) reply = "나중에 fetch('/api/chat') 부분만 실제 엔드포인트로 바꾸세요. 바디는 {messages:[...]} 형태 추천!";
    else if (/react|리액트/.test(lower)) reply = "이 컴포넌트는 React + CSS 분리로 작성됐어요. 어떤 페이지에도 바로 붙일 수 있어요.";
    else if (/bookbridge|북브릿지|공지|폼|datepicker|카카오/.test(lower)) reply = "BookBridge 스타일에도 쉽게 이식 가능합니다. UI만 유지하고 응답부만 실제 API로 교체하세요.";

    await new Promise((r) => setTimeout(r, 500));
    await streamFake(reply);
    setIsLoading(false);
  }

  function clearChat() {
    setMessages([{ id: crypto.randomUUID(), role: "assistant", text: "대화를 초기화했어요. 무엇을 도와드릴까요?" }]);
  }

  // 🔎 메시지 전체 검색 (query 변경 시 결과 생성)
  useEffect(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      setResults([]);
      return;
    }
    const r = [];
    for (const m of messages) {
      const t = m.text.toLowerCase();
      const idx = t.indexOf(q);
      if (idx !== -1) {
        r.push({ id: m.id, role: m.role, text: m.text, indices: [idx, idx + q.length] });
      }
    }
    setResults(r);
  }, [query, messages]);

  function scrollToMessage(id) {
    const el = msgRefs.current.get(id);
    if (!el || !listRef.current) return;
    const container = listRef.current;
    const top = el.offsetTop - container.clientHeight / 4;
    container.scrollTo({ top, behavior: "smooth" });
    el.classList.add("cc-ring");
    setTimeout(() => el.classList.remove("cc-ring"), 1200);
  }

  function Highlight({ text, start, end }) {
    if (start == null || end == null || start < 0) return text;
    return (
      <>
        {text.slice(0, start)}
        <mark className="cc-mark">{text.slice(start, end)}</mark>
        {text.slice(end)}
      </>
    );
  }

  const rootClass = `cc-app theme--${theme}`;

  return (
    <div className={rootClass}>
      <div className="cc-container">
        <header className="cc-header">
          <div className="cc-title">
            <Bot size={20} />
            <h1>AI Chatbot</h1>
          </div>
          <div className="cc-actions">
            <button className="cc-btn" title="이전 대화 검색" onClick={() => setSearchOpen((v) => !v)}>
              <Search size={16} /> 검색
            </button>
            <button className="cc-btn" onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}>
              {theme === "dark" ? "라이트" : "다크"}
            </button>
            <button className="cc-btn" onClick={clearChat}>
              <span className="cc-icon"><Loader2 size={0} /></span>
              초기화
            </button>
          </div>
        </header>

        {searchOpen && (
          <div className="cc-search">
            <div className="cc-search-row">
              <Search size={16} className="cc-search-icon" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="이전 대화 검색 (키워드 입력)"
                className="cc-search-input"
              />
              {query && (
                <button onClick={() => setQuery("")} className="cc-search-clear" title="지우기">
                  <X size={16} />
                </button>
              )}
            </div>
            {query && <div className="cc-search-meta">결과 {results.length}개</div>}
            {query && results.length > 0 && (
              <ul className="cc-search-results">
                {results.map((r) => (
                  <li key={r.id} className="cc-search-item">
                    <span className={`cc-avatar ${r.role === "assistant" ? "is-assistant" : "is-user"}`}>
                      {r.role === "assistant" ? <Bot size={14} /> : <User size={14} />}
                    </span>
                    <button className="cc-search-link" onClick={() => scrollToMessage(r.id)} title="이 위치로 이동">
                      <Highlight text={r.text} start={r.indices[0]} end={r.indices[1]} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* ✅ 대화 + 입력 합쳐진 카드 */}
        <div className="cc-card">
          {/* 채팅 리스트 */}
          <div ref={listRef} className="cc-chat-list">
            <ul className="cc-list">
              {messages.map((m) => (
                <li key={m.id} className="cc-row">
                  <div className={`cc-avatar ${m.role === "assistant" ? "is-assistant" : "is-user"}`} title={m.role}>
                    {m.role === "assistant" ? <Bot size={18} /> : <User size={18} />}
                  </div>
                  <motion.div
                    ref={(el) => el && msgRefs.current.set(m.id, el)}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className={`cc-bubble ${m.role === "assistant" ? "is-assistant" : "is-user"}`}
                  >
                    {m.text}
                  </motion.div>
                </li>
              ))}

              {isLoading && (
                <li className="cc-row cc-loading">
                  <Loader2 className="cc-spin" size={16} />
                  <span>응답 생성 중…</span>
                </li>
              )}
            </ul>
          </div>

          {/* 입력 영역 */}
          <form onSubmit={onSubmit} className="cc-input-area">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={placeholder}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) onSubmit(e);
              }}
              rows={1}
              className="cc-textarea"
            />
            <div className="cc-input-bar">
              <small>Enter=전송, Shift+Enter=줄바꿈</small>
              <button type="submit" className="cc-btn-primary" disabled={isLoading}>
                <Send size={16} /> 보내기
              </button>
            </div>
          </form>
        </div>

        {/* 질문 기록 (간단 목록) */}
        {history.length > 0 && (
          <div className="cc-history">
            <div className="cc-history-title">
              <History size={16} /> 최근 질문들
            </div>
            <ul className="cc-history-list">
              {history.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
