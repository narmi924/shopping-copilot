import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRightOutlined,
  ArrowUpOutlined,
  BarChartOutlined,
  PlusOutlined,
  SlidersOutlined,
  StarFilled,
} from "@ant-design/icons";
import { Alert, Button, Drawer, Input, Modal, Spin, Tag } from "antd";
import { createSession, getMetrics, sendTurn } from "./api";
import type {
  ChatEntry,
  DebugSnapshot,
  MetricsResponse,
  ProductRecommendation,
} from "./types";

const { TextArea } = Input;

const QUICK_PROMPTS = [
  "Women's breathable mesh sneakers under $80",
  "A 40L airline-approved carry-on backpack for adults",
  "A women's warm wool coat for a rainy winter",
];

const INITIAL_MESSAGES: ChatEntry[] = [
  {
    id: "welcome",
    role: "agent",
    turn: 0,
    content: "Describe the product you need. I’ll return up to 10 recommendations and ask one clarifying question.",
  },
];

const SCENARIO_LABELS: Record<string, string> = {
  buying: "Buying",
  browsing: "Browsing",
  intent_override: "Changed intent",
  boundary: "No preference",
};

const ROUTE_LABELS: Record<string, string> = {
  buying: "Ready to buy",
  browsing: "Exploring",
  override: "Direction updated",
};

const SOURCE_LABELS: Record<string, string> = {
  current: "Latest request",
  current_message: "Latest request",
  active: "Saved preferences",
  active_constraints: "Saved preferences",
  stable: "Shopping context",
  stable_context: "Shopping context",
  profile: "Profile hints",
  evidence: "Exact catalog evidence",
  strict: "All-term precision",
};

function humanize(value: string | null | undefined): string {
  if (!value) return "None";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function routeLabel(route: string | null | undefined): string {
  return route ? ROUTE_LABELS[route] ?? humanize(route) : "Ready";
}

function formatPrice(value: number | null): string {
  return value === null
    ? "Price unavailable"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      }).format(value);
}

function formatMetric(value: number | null, digits = 3): string {
  return value === null ? "—" : Number(value).toFixed(digits);
}

function activePreferenceValues(debug: DebugSnapshot | null): string[] {
  if (!debug) return [];
  return Object.entries(debug.active_constraints).flatMap(([attribute, values]) =>
    values.map((value) => `${humanize(attribute)}: ${value}`),
  );
}

function ProductCard({ product, rank }: { product: ProductRecommendation; rank: number }) {
  const category = product.categories.slice(-2).join(" · ") || "General merchandise";
  return (
    <article className="product-card">
      <div className="product-card-topline">
        <span className="product-rank">Match {String(rank).padStart(2, "0")}</span>
        <strong className="product-price">{formatPrice(product.price)}</strong>
      </div>

      <div className="product-copy">
        <p className="product-category" title={category}>{category}</p>
        <h3>{product.title}</h3>
        <p className="product-feature">
          {product.feature || "No feature summary available."}
        </p>
      </div>

      <div className="product-details">
        <span className="store-name" title={product.store}>{product.store}</span>
        <span className="rating-line" aria-label={`${product.average_rating ?? "No"} star rating`}>
          <StarFilled aria-hidden="true" />
          {product.average_rating?.toFixed(1) ?? "—"}
          <small>{product.rating_number > 0 ? product.rating_number.toLocaleString() : "No reviews"}</small>
        </span>
      </div>

      <div className="product-id">
        <span>ASIN</span>
        <code>{product.parent_asin}</code>
      </div>
    </article>
  );
}

function ContextDrawer({
  debug,
  open,
  onClose,
}: {
  debug: DebugSnapshot | null;
  open: boolean;
  onClose: () => void;
}) {
  const preferences = activePreferenceValues(debug);

  return (
    <Drawer
      title="Recommendation context"
      placement="right"
      size={440}
      open={open}
      onClose={onClose}
      className="context-drawer"
    >
      <p className="drawer-intro">
        Constraints and session state used for the current ranking.
      </p>

      <section className="drawer-section">
        <span className="drawer-label">Detected route</span>
        <h3>{routeLabel(debug?.detected_route)}</h3>
        {debug?.detected_route === "override" && (
          <p>Previous soft constraints were superseded before retrieval.</p>
        )}
      </section>

      <section className="drawer-section">
        <span className="drawer-label">Active constraints</span>
        <div className="drawer-tags">
          {preferences.length > 0 ? (
            preferences.map((item) => <Tag key={item}>{item}</Tag>)
          ) : (
            <p className="empty-note">No active constraints.</p>
          )}
        </div>
      </section>

      {(debug?.declined_attributes.length ?? 0) > 0 && (
        <section className="drawer-section">
          <span className="drawer-label">No preference</span>
          <p>{debug?.declined_attributes.map(humanize).join(", ")}</p>
        </section>
      )}

      {(debug?.exhausted_attributes.length ?? 0) > 0 && (
        <section className="drawer-section">
          <span className="drawer-label">No additional preference</span>
          <p>{debug?.exhausted_attributes.map(humanize).join(", ")}</p>
        </section>
      )}

      <section className="drawer-section">
        <span className="drawer-label">Last asked attribute</span>
        <h3>{debug?.last_asked_attribute ? humanize(debug.last_asked_attribute) : "Nothing yet"}</h3>
      </section>

      {(debug?.superseded_constraints.length ?? 0) > 0 && (
        <section className="drawer-section">
          <span className="drawer-label">Superseded constraints</span>
          <div className="superseded-list">
            {debug?.superseded_constraints.map((item, index) => (
              <span key={`${item.attribute}-${item.value}-${index}`}>
                {humanize(item.attribute)}: {item.value}
              </span>
            ))}
          </div>
        </section>
      )}

      {(debug?.negative_constraints.length ?? 0) > 0 && (
        <section className="drawer-section">
          <span className="drawer-label">Excluded preferences</span>
          <div className="superseded-list">
            {debug?.negative_constraints.map((item, index) => (
              <span key={`${item.attribute}-${item.value}-${index}`}>
                {humanize(item.attribute)}: {item.value}
              </span>
            ))}
          </div>
        </section>
      )}

      <details className="technical-details">
        <summary>Technical details</summary>
        {debug ? (
          <div className="technical-content">
            <div className="technical-stat">
              <span>Candidate pool</span>
              <strong>{debug.candidate_count}</strong>
            </div>
            <div className="source-list">
              <span className="drawer-label">Retrieval evidence</span>
              {Object.entries(debug.retrieval_sources).map(([name, source]) => (
                <div className="source-row" key={name}>
                  <span>{SOURCE_LABELS[name] ?? humanize(name)}</span>
                  <small>
                    {source.candidate_count} candidates
                    {source.mode === "exact-evidence" ? " · exact match" : ""}
                  </small>
                </div>
              ))}
            </div>
            {debug.question_value?.attribute && (
              <div className="source-list">
                <span className="drawer-label">Selected question</span>
                <div className="technical-stat">
                  <span>{humanize(debug.question_value.attribute)}</span>
                  <strong>{(debug.question_value.score ?? 0).toFixed(3)}</strong>
                </div>
                {Object.entries(debug.question_value.factors ?? {}).map(([name, value]) => (
                  <div className="source-row" key={name}>
                    <span>{humanize(name)}</span>
                    <small>{value.toFixed(3)}</small>
                  </div>
                ))}
              </div>
            )}
            {(debug.candidate_portfolio?.precision_count ?? 0) > 0 && (
              <div className="source-list">
                <span className="drawer-label">Top 10 allocation</span>
                <div className="source-row">
                  <span>Precision core</span>
                  <small>{debug.candidate_portfolio.precision_count ?? 0} slots</small>
                </div>
                <div className="source-row">
                  <span>Exploration tail</span>
                  <small>{debug.candidate_portfolio.exploration_count ?? 0} slots</small>
                </div>
              </div>
            )}
            <div className="ranking-list">
              <span className="drawer-label">Top ranking scores</span>
              {debug.final_ranking_scores.slice(0, 5).map((item, index) => (
                <div className="ranking-row" key={item.parent_asin}>
                  <span>{index + 1}</span>
                  <code>{item.parent_asin}</code>
                  <strong>{item.score.toFixed(4)}</strong>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="empty-note">Details appear after your first request.</p>
        )}
      </details>
    </Drawer>
  );
}

function PerformanceModal({
  open,
  metrics,
  error,
  onClose,
  onRetry,
}: {
  open: boolean;
  metrics: MetricsResponse | null;
  error: boolean;
  onClose: () => void;
  onRetry: () => void;
}) {
  const headlineMetrics = metrics
    ? ([
        ["Hit Rate@10", metrics.candidate.hit_rate_at_10, metrics.baseline.hit_rate_at_10, false],
        ["MRR", metrics.candidate.mrr, metrics.baseline.mrr, false],
        ["MTTC", metrics.candidate.mttc, metrics.baseline.mttc, true],
        [
          "Technical score",
          metrics.candidate.recommended_technical_score,
          metrics.baseline.recommended_technical_score,
          false,
        ],
      ] as const)
    : [];

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={780}
      className="performance-modal"
      title={null}
    >
      <div className="performance-heading">
        <h2>Evaluation results</h2>
        <p>Official public evaluation · 200 sessions</p>
      </div>

      {error ? (
        <Alert
          type="warning"
          showIcon
          title="Performance results are unavailable."
          action={<Button size="small" onClick={onRetry}>Retry</Button>}
        />
      ) : metrics ? (
        <>
          <div className="metric-grid">
            {headlineMetrics.map(([label, candidate, baseline, lowerIsBetter]) => {
              const improvement = lowerIsBetter
                ? Number(baseline) - Number(candidate)
                : Number(candidate) - Number(baseline);
              return (
                <article className="metric-card" key={label}>
                  <span>{label}</span>
                  <strong>{formatMetric(candidate, label === "MTTC" ? 2 : 3)}</strong>
                  <small>
                    {improvement >= 0 ? "+" : ""}{improvement.toFixed(3)} vs baseline
                  </small>
                </article>
              );
            })}
          </div>

          <div className="scenario-list">
            {Object.entries(metrics.candidate.scenario_metrics).map(([scenario, value]) => {
              const baseline = metrics.baseline.scenario_metrics[scenario];
              return (
                <article className="scenario-row" key={scenario}>
                  <div>
                    <span>{SCENARIO_LABELS[scenario] ?? humanize(scenario)}</span>
                    <small>Hit Rate@10</small>
                  </div>
                  <div className="scenario-track" aria-hidden="true">
                    <i style={{ width: `${Math.min(100, value.hit_rate_at_10 * 100)}%` }} />
                  </div>
                  <strong>{value.hit_rate_at_10.toFixed(3)}</strong>
                  <small>baseline {baseline?.hit_rate_at_10.toFixed(3) ?? "—"}</small>
                </article>
              );
            })}
          </div>
        </>
      ) : (
        <div className="modal-loading"><Spin /> Loading performance…</div>
      )}
    </Modal>
  );
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatEntry[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<ProductRecommendation[]>([]);
  const [debug, setDebug] = useState<DebugSnapshot | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [metricsError, setMetricsError] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [performanceOpen, setPerformanceOpen] = useState(false);
  const [newSearchOpen, setNewSearchOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const loadMetrics = useCallback(async () => {
    setMetricsError(false);
    try {
      setMetrics(await getMetrics());
    } catch {
      setMetricsError(true);
    }
  }, []);

  useEffect(() => {
    void loadMetrics();
  }, [loadMetrics]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages]);

  const currentTurn = debug?.turn_count ?? 0;
  const preferences = useMemo(() => activePreferenceValues(debug), [debug]);
  const statusLabel = useMemo(() => {
    if (busy && !sessionId) return "Preparing search";
    if (busy) return "Finding matches";
    return sessionId ? "Search active" : "Ready";
  }, [busy, sessionId]);

  async function handleSend(proposed?: string) {
    const content = (proposed ?? input).trim();
    if (!content || busy) return;

    const nextTurn = currentTurn + 1;
    const messageId = `user-${Date.now()}`;
    setInput("");
    setBusy(true);
    setError(null);
    setMessages((current) => [
      ...current,
      { id: messageId, role: "user", content, turn: nextTurn },
    ]);

    try {
      const activeSession = sessionId ?? (await createSession());
      if (!sessionId) setSessionId(activeSession);
      const response = await sendTurn(activeSession, content);
      setMessages((current) => [
        ...current,
        {
          id: `agent-${Date.now()}`,
          role: "agent",
          content: response.message,
          turn: response.turn,
          askAttribute: response.ask_attribute,
        },
      ]);
      setRecommendations(response.recommendations);
      setDebug(response.debug);
    } catch (caught) {
      setMessages((current) => current.filter((message) => message.id !== messageId));
      setInput(content);
      setError(caught instanceof Error ? caught.message : "The local service could not respond.");
    } finally {
      setBusy(false);
    }
  }

  function startNewSearch() {
    if (busy) return;
    setSessionId(null);
    setMessages(INITIAL_MESSAGES);
    setRecommendations([]);
    setDebug(null);
    setError(null);
    setInput("");
    setContextOpen(false);
    setNewSearchOpen(false);
  }

  function requestNewSearch() {
    if (busy) return;
    if (currentTurn === 0) {
      startNewSearch();
      return;
    }
    setNewSearchOpen(true);
  }

  return (
    <div className="app-shell">
      <header className="site-nav">
        <div className="nav-inner">
          <a className="wordmark" href="#top" aria-label="Shopping Copilot home">
            <span className="wordmark-mark" aria-hidden="true"><i /><i /></span>
            <span>Shopping Copilot</span>
          </a>
          <div className="nav-actions">
            <button
              className="nav-link"
              type="button"
              aria-label="View performance"
              onClick={() => setPerformanceOpen(true)}
            >
              <BarChartOutlined aria-hidden="true" />
              <span>Performance</span>
            </button>
            <Button
              className="new-search-button"
              icon={<PlusOutlined />}
              onClick={requestNewSearch}
              disabled={busy}
            >
              New search
            </Button>
          </div>
        </div>
      </header>

      <main id="top">
        <section className="workspace" aria-label="Shopping workspace">
          <aside className="conversation-column">
            <section className="conversation-card" aria-labelledby="conversation-title">
              <div className="conversation-header">
                <h2 id="conversation-title">Conversation</h2>
                <span className="session-status"><i aria-hidden="true" />{statusLabel}</span>
              </div>

              <div className="message-list" aria-live="polite" aria-busy={busy}>
                {messages.map((message) => (
                  <article className={`message message-${message.role}`} key={message.id}>
                    <div className="message-meta">
                      <span>{message.role === "user" ? "You" : "Copilot"}</span>
                      <span>{message.turn === 0 ? "Welcome" : `Turn ${message.turn}`}</span>
                    </div>
                    <p>{message.content}</p>
                    {message.askAttribute && (
                      <span className="asked-attribute">
                        Refining {humanize(message.askAttribute)}
                      </span>
                    )}
                  </article>
                ))}
                {busy && (
                  <article className="message message-agent loading-message">
                    <Spin size="small" />
                    <span>{sessionId ? "Finding your best matches…" : "Preparing the catalog…"}</span>
                  </article>
                )}
                <div ref={messagesEndRef} />
              </div>

              {error && <Alert type="error" showIcon title={error} className="error-alert" />}

              {currentTurn === 0 && !busy && (
                <div className="prompt-suggestions" aria-label="Example shopping requests">
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => void handleSend(prompt)}
                    >
                      {prompt}<ArrowRightOutlined aria-hidden="true" />
                    </button>
                  ))}
                </div>
              )}

              <div className="composer">
                <TextArea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onPressEnter={(event) => {
                    if (!event.shiftKey) {
                      event.preventDefault();
                      void handleSend();
                    }
                  }}
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  placeholder="Tell me what you need…"
                  aria-label="Shopping request"
                  disabled={busy}
                />
                <Button
                  type="primary"
                  shape="circle"
                  icon={<ArrowUpOutlined />}
                  aria-label="Send request"
                  onClick={() => void handleSend()}
                  loading={busy}
                  disabled={!input.trim()}
                />
              </div>

              <div className="context-summary">
                <div className="context-copy">
                  <span>Shopping context</span>
                  <p>
                    {preferences.length > 0
                      ? preferences.slice(0, 3).join(" · ")
                      : "Preferences will appear as we talk."}
                  </p>
                </div>
                <button type="button" className="context-link" onClick={() => setContextOpen(true)}>
                  <SlidersOutlined aria-hidden="true" />
                  Details
                </button>
              </div>

              <div className="conversation-footer">
                <span>Turn {currentTurn}</span>
                <span>{routeLabel(debug?.detected_route)}</span>
                <span>
                  {debug?.last_asked_attribute
                    ? `Asking: ${humanize(debug.last_asked_attribute)}`
                    : "No open question"}
                </span>
                {recommendations.length > 0 && (
                  <a href="#recommendations">{recommendations.length} matches</a>
                )}
              </div>
            </section>
          </aside>

          <section className="recommendations-column" id="recommendations" aria-labelledby="recommendations-title">
            <div className="recommendations-header">
              <h2 id="recommendations-title">Recommendations</h2>
              <p aria-live="polite">
                {recommendations.length > 0
                  ? `${recommendations.length} products ranked for this session`
                  : "No products ranked yet"}
              </p>
            </div>

            {recommendations.length > 0 ? (
              <div className="product-grid">
                {recommendations.map((product, index) => (
                  <ProductCard key={product.parent_asin} product={product} rank={index + 1} />
                ))}
              </div>
            ) : (
              <div className="recommendation-empty">
                <div>
                  <h3>No recommendations yet</h3>
                  <p>Enter a shopping request to begin.</p>
                </div>
              </div>
            )}
          </section>
        </section>
      </main>

      <ContextDrawer debug={debug} open={contextOpen} onClose={() => setContextOpen(false)} />
      <PerformanceModal
        open={performanceOpen}
        metrics={metrics}
        error={metricsError}
        onClose={() => setPerformanceOpen(false)}
        onRetry={() => void loadMetrics()}
      />
      <Modal
        open={newSearchOpen}
        title="Start a new search?"
        okText="Start new search"
        cancelText="Keep shopping"
        onOk={startNewSearch}
        onCancel={() => setNewSearchOpen(false)}
        centered
      >
        <p>Your current conversation and shortlist will be cleared.</p>
      </Modal>
    </div>
  );
}
