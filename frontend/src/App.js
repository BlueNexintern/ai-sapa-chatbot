/** App.js */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Send, Bot, User, Loader2, History, Search, X, Sun, Moon, Image as ImageIcon, CheckSquare, Square } from "lucide-react";
import { motion } from "framer-motion";
import "./App.css"; /** 스타일 분리 */

export default function App() {
  const [messages, setMessages] = useState([
    { id: crypto.randomUUID(), role: "assistant", text: "안녕하세요! 가짜 AI 챗봇 더미입니다. 무엇을 도와드릴까요?" },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [theme, setTheme] = useState("light"); /** "light" | "dark" */

  /**
   * 최근 질문(최대 10) - label을 저장하여 텍스트가 없어도(이미지만) 기록되도록 함
   * 형태: [{ id: string, text: string }]
   */
  const [history, setHistory] = useState([]);

  /** 최근 질문 편집 모드 & 선택 상태 */
  const [historyEdit, setHistoryEdit] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState(new Set());

  /** 🔎 검색 상태 */
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [results, setResults] = useState([]); /** {id, role, text, start, end} */

  /** 사진 첨부 상태: [{id, name, url}] (dataURL) */
  const [attachments, setAttachments] = useState([]);

  const listRef = useRef(null);
  const msgRefs = useRef(new Map()); /** id -> <li> 엘리먼트 */
  const fileRef = useRef(null);      /** 숨김 파일 입력 */

  /** 스크롤 하단 고정 */
  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isLoading]);

  /** placeholder 메모 */
  const placeholder = useMemo(
    () => (isLoading ? "응답 생성 중…" : "메시지를 입력하세요 (Enter=전송, Shift+Enter=줄바꿈)"),
    [isLoading]
  );

  /** 간단 타이핑 효과 (버블 재마운트 방지) */
  function streamFake(text, speed = 12) {
    return new Promise((resolve) => {
      let i = 0;
      const id = crypto.randomUUID();
      setMessages((prev) => [...prev, { id, role: "assistant", text: "" }]);
      const interval = setInterval(() => {
        i += 1;
        setMessages((prev) =>
          prev.map((m) => (m.id === id ? { ...m, text: text.slice(0, i) } : m))
        );
        if (i >= text.length) {
          clearInterval(interval);
          resolve();
        }
      }, speed);
    });
  }

  /** 파일 → dataURL로 변환 */
  function filesToDataUrls(fileList) {
    const limit = 5; /** 최대 5장 */
    const current = attachments.length;
    const canTake = Math.max(0, limit - current);
    const picked = Array.from(fileList || []).slice(0, canTake);

    Promise.all(
      picked.map(
        (file) =>
          new Promise((res) => {
            const reader = new FileReader();
            reader.onload = () =>
              res({ id: crypto.randomUUID(), name: file.name, url: reader.result });
            reader.readAsDataURL(file);
          })
      )
    ).then((items) => setAttachments((prev) => [...prev, ...items]));
  }

  /** 파일 선택 트리거 */
  function openPicker() {
    fileRef.current?.click();
  }

  /** 파일 선택 변경 */
  function onPickFiles(e) {
    filesToDataUrls(e.target.files);
    e.target.value = ""; /** 동일 파일 재선택 가능하도록 초기화 */
  }

  /** 개별 첨부 삭제 */
  function removeAttachment(id) {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }

  /** 이미지 전용/혼합 전송 시 표시용 레이블 생성 */
  function buildAttachmentLabel(items) {
    const n = items.length;
    if (n === 0) return "";
    const names = items.map((a) => a.name).filter(Boolean);
    if (names.length === 0) return `이미지 ${n}장`;
    const head = names.slice(0, 2).join(", ");
    return n > 2 ? `이미지 ${n}장 (${head} 외)` : `이미지 ${n}장 (${head})`;
  }

  /** 메시지 전송 */
  async function onSubmit(e) {
    e?.preventDefault();
    const trimmed = input.trim();
    const hasText = trimmed.length > 0;
    const hasImages = attachments.length > 0;
    const canSend = hasText || hasImages;
    if (!canSend || isLoading) return;

    /** 검색/최근질문용 label (텍스트 없으면 이미지 레이블로 대체) */
    const label = hasText ? trimmed : buildAttachmentLabel(attachments);

    const userMsg = {
      id: crypto.randomUUID(),
      role: "user",
      text: hasText ? trimmed : "",                 /** 텍스트 없으면 빈 문자열 */
      attachments: attachments.map((a) => ({ name: a.name, url: a.url })),
      label                                          /** 검색/최근질문용 표시 텍스트 */
    };

    /** 메시지 목록에 추가 */
    setMessages((prev) => [...prev, userMsg]);

    /** 최근 질문 기록: 항상 label로 추가 (이미지만 보내도 기록됨) */
    setHistory((prev) => [{ id: userMsg.id, text: label }, ...prev].slice(0, 10));

    /** 입력/첨부/상태 업데이트 */
    setInput("");
    setAttachments([]);
    setIsLoading(true);

    /** 더미 답변 결정 */
    const lower = trimmed.toLowerCase();
    let reply = "좋은 질문이에요! 하지만 저는 더미에요. 진짜 모델을 연결하면 훨씬 똑똑해져요.";

    if (/(hello|hi|안녕)/.test(lower)) reply = "안녕하세요! 무엇을 만들어볼까요?";
    else if (/help|도움|사용법/.test(lower)) reply = "아래 입력창에 질문을 쓰고 Enter를 누르세요. 나중에 /api/chat을 실제 백엔드로 연결하면 됩니다.";
    else if (/api|연결|백엔드|서버/.test(lower)) reply = "나중에 fetch('/api/chat') 부분만 실제 엔드포인트로 바꾸세요. 바디는 {messages:[...]} 형태 추천!";
    else if (/react|리액트/.test(lower)) reply = "이 컴포넌트는 React + CSS 분리로 작성됐어요. 어떤 페이지에도 바로 붙일 수 있어요.";
    else if (/bookbridge|북브릿지|공지|폼|datepicker|카카오/.test(lower)) reply = "BookBridge 스타일에도 쉽게 이식 가능합니다. UI만 유지하고 응답부만 실제 API로 교체하세요.";

    /** 더미 응답 대기 + 타이핑 */
    await new Promise((r) => setTimeout(r, 500));
    await streamFake(reply);
    setIsLoading(false);
  }

  /** Enter=전송 / Shift+Enter=줄바꿈 */
  function onTextareaKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  }

  /** 검색 결과 계산
   *  - 우선순위: m.text → m.label → 첨부 파일명
   *  - 이미지 전용 메시지도 검색에 잡히도록 처리
   */
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const q = query.toLowerCase();
    const found = [];

    messages.forEach((m) => {
      const filenames = Array.isArray(m.attachments)
        ? m.attachments.map((a) => a?.name || "").join(" ")
        : "";
      const display = (m.text && m.text.trim())
        ? m.text
        : (m.label || filenames || "");
      const hay = (display || "").toLowerCase();
      const idx = hay.indexOf(q);
      if (idx !== -1 && display) {
        found.push({
          id: m.id,
          role: m.role,
          text: display,
          start: idx,
          end: idx + q.length
        });
      }
    });

    setResults(found);
  }, [query, messages]);

  /** 특정 메시지로 스크롤 + 하이라이트 링 */
  function jumpToMessage(id) {
    const li = msgRefs.current.get(id);
    if (!li || !listRef.current) return;
    const top = li.offsetTop - 12;
    listRef.current.scrollTo({ top, behavior: "smooth" });
    li.classList.add("cc-ring");
    setTimeout(() => li.classList.remove("cc-ring"), 900);
  }

  /** 말풍선 콘텐츠 (검색 하이라이트 반영) */
  function renderBubbleText(m) {
    if (!m.text) return null; /** 이미지 전용 메시지는 버블 자체를 렌더하지 않음 */
    if (!query.trim()) return m.text;
    const q = query.toLowerCase();
    const t = m.text;
    const idx = t.toLowerCase().indexOf(q);
    if (idx === -1) return t;
    const before = t.slice(0, idx);
    const mid = t.slice(idx, idx + q.length);
    const after = t.slice(idx + q.length);
    return (
      <>
        {before}
        <mark className="cc-mark">{mid}</mark>
        {after}
      </>
    );
  }

  /** 검색 결과용 스니펫 렌더 */
  function renderSearchSnippet(r) {
    const before = r.text.slice(Math.max(0, r.start - 12), r.start);
    const mid = r.text.slice(r.start, r.end);
    const after = r.text.slice(r.end, Math.min(r.text.length, r.end + 24));
    return (
      <>
        …{before}
        <mark className="cc-mark">{mid}</mark>
        {after}…
      </>
    );
  }

  /** ====== 최근 질문: 편집/선택/삭제 ====== */
  function toggleHistoryEdit() {
    setHistoryEdit((v) => !v);
    setSelectedHistory(new Set());
  }
  function onToggleSelect(id) {
    setSelectedHistory((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function deleteSelected() {
    if (selectedHistory.size === 0) return;
    setHistory((prev) => prev.filter((h) => !selectedHistory.has(h.id)));
    setSelectedHistory(new Set());
    setHistoryEdit(false);
  }
  function deleteAll() {
    setHistory([]);
    setSelectedHistory(new Set());
    setHistoryEdit(false);
  }

  return (
    <div className={`cc-app theme--${theme}`}>
      <div className="cc-container">
        {/* 헤더 */}
        <header className="cc-header">
          <div className="cc-title">
            <Bot size={20} />
            <h1>AI 챗봇 (더미)</h1>
          </div>
          <div className="cc-actions">
            <button
              className="cc-btn"
              onClick={() => setSearchOpen((v) => !v)}
              aria-pressed={searchOpen}
              title="대화 내 검색"
            >
              <Search size={16} /> 검색
            </button>
            <button
              className="cc-btn"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              title="테마 전환"
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />} 테마
            </button>
          </div>
        </header>

        {/* 검색 패널 */}
        {searchOpen && (
          <div className="cc-search">
            <div className="cc-search-row">
              <Search className="cc-search-icon" size={16} />
              <input
                className="cc-search-input"
                type="text"
                placeholder="대화 내용에서 검색…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {query && (
                <button className="cc-search-clear" onClick={() => setQuery("")} title="지우기">
                  <X size={16} />
                </button>
              )}
            </div>
            <div className="cc-search-meta">
              {query ? `검색 결과: ${results.length}개` : "키워드를 입력해 검색하세요."}
            </div>
            {!!results.length && (
              <ul className="cc-search-results">
                {results.map((r) => (
                  <li key={`res-${r.id}`} className="cc-search-item">
                    <button className="cc-search-link" onClick={() => jumpToMessage(r.id)}>
                      {renderSearchSnippet(r)}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* 카드 & 채팅 */}
        <div className="cc-card">
          <div className="cc-chat-list" ref={listRef}>
            <ul className="cc-list">
              {messages.map((m) => (
                <li
                  key={m.id}
                  className={`cc-row is-${m.role}`}
                  ref={(el) => msgRefs.current.set(m.id, el)}
                >
                  <div className={`cc-avatar is-${m.role}`}>
                    {m.role === "assistant" ? <Bot size={16} /> : <User size={16} />}
                  </div>

                  {/** 버블+첨부를 세로 스택으로 묶는 컨텐츠 래퍼 */}
                  <div className="cc-content">
                    {m.text && (
                      <motion.div
                        className={`cc-bubble is-${m.role}`}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.16 }}
                      >
                        {renderBubbleText(m)}
                      </motion.div>
                    )}

                    {Array.isArray(m.attachments) && m.attachments.length > 0 && (
                      <div className="cc-msg-attachments">
                        {m.attachments.map((att, i) => {
                          const src = typeof att === "string" ? att : att.url;
                          return <img key={`${m.id}-att-${i}`} src={src} alt="attachment" className="cc-thumb" />;
                        })}
                      </div>
                    )}
                  </div>
                </li>
              ))}
              {isLoading && (
                <li className="cc-row is-assistant cc-loading">
                  <Loader2 className="cc-spin" size={16} /> 입력 중…
                </li>
              )}
            </ul>
          </div>

          {/* 입력 영역: 왼쪽(사진) + 가운데(입력창) + 오른쪽(전송) */}
          <form className="cc-input-area" onSubmit={onSubmit}>
            <div className="cc-input-row">
              <button
                type="button"
                className="cc-attach-btn"
                onClick={openPicker}
                title="사진 추가"
                aria-label="사진 추가"
              >
                <ImageIcon size={18} />
              </button>

              <textarea
                className="cc-textarea"
                placeholder={placeholder}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onTextareaKeyDown}
                rows={1}
              />

              <button
                type="submit"
                className="cc-btn-primary"
                disabled={(!input.trim() && attachments.length === 0) || isLoading}
                title="전송"
              >
                <Send size={16} /> 전송
              </button>

              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                multiple
                className="cc-file"
                onChange={onPickFiles}
              />
            </div>

            {attachments.length > 0 && (
              <div className="cc-attachments">
                {attachments.map((a) => (
                  <div key={a.id} className="cc-attach-item">
                    <img src={a.url} alt={a.name} className="cc-thumb" />
                    <button
                      type="button"
                      className="cc-attach-remove"
                      onClick={() => removeAttachment(a.id)}
                      title="삭제"
                      aria-label="첨부 삭제"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="cc-input-hint">
              <small>
                Enter=전송, Shift+Enter=줄바꿈 {attachments.length > 0 ? `• 첨부 ${attachments.length}개` : ""}
              </small>
            </div>
          </form>
        </div>

        {/* 히스토리 */}
        {/* <div className="cc-history">
          <div className="cc-history-title">
            <History size={16} />
            <strong>최근 질문</strong>
            <div className="cc-history-title-actions">
              {history.length > 0 && (
                <button className="cc-btn" onClick={toggleHistoryEdit} title="편집">
                  {historyEdit ? "완료" : "편집"}
                </button>
              )}
            </div>
          </div>

          {history.length === 0 ? (
            <p className="cc-history-empty">아직 기록이 없습니다.</p>
          ) : (
            <>
              <ol className="cc-history-list">
                {history.map((h) => {
                  const isSelected = selectedHistory.has(h.id);
                  if (historyEdit) {
                    return (
                      <li key={h.id} className="cc-history-row">
                        <button
                          type="button"
                          className="cc-history-select"
                          onClick={() => onToggleSelect(h.id)}
                          aria-pressed={isSelected}
                          title={isSelected ? "선택 해제" : "선택"}
                        >
                          {isSelected ? <CheckSquare size={16} /> : <Square size={16} />}
                        </button>
                        <button
                          className="cc-history-text"
                          onClick={() => onToggleSelect(h.id)}
                          title="선택/해제"
                        >
                          {h.text}
                        </button>
                      </li>
                    );
                  }
                  return (
                    <li key={h.id} className="cc-history-row">
                      <button
                        className="cc-history-text cc-search-link"
                        onClick={() => jumpToMessage(h.id)}
                        title="해당 메시지 위치로 이동"
                      >
                        {h.text}
                      </button>
                    </li>
                  );
                })}
              </ol>

              {historyEdit ? (
                <div className="cc-history-actions">
                  <button
                    className="cc-btn"
                    onClick={deleteSelected}
                    disabled={selectedHistory.size === 0}
                    title="선택 항목 삭제"
                  >
                    <X size={16} /> 선택 삭제{selectedHistory.size > 0 ? ` (${selectedHistory.size})` : ""}
                  </button>
                  <button className="cc-btn" onClick={deleteAll} title="전체 삭제">
                    <X size={16} /> 전체 삭제
                  </button>
                </div>
              ) : (
                <div className="cc-history-actions">
                  <button className="cc-btn" onClick={deleteAll} title="전체 삭제">
                    <X size={16} /> 전체 삭제
                  </button>
                </div>
              )}
            </>
          )}
        </div> */}
      </div>
    </div>
  );
}
