export interface ProductRecommendation {
  parent_asin: string;
  title: string;
  price: number | null;
  categories: string[];
  store: string;
  average_rating: number | null;
  rating_number: number;
  feature: string;
  ranking_score: number;
}

export interface RetrievalSource {
  weight: number;
  candidate_count: number;
  mode: "any-term" | "all-terms";
  terms: string[];
}

export interface DebugSnapshot {
  session_id: string;
  detected_route: "buying" | "browsing" | "override";
  active_constraints: Record<string, string[]>;
  superseded_constraints: Array<{ attribute: string; value: string }>;
  asked_attributes: string[];
  declined_attributes: string[];
  last_asked_attribute: string | null;
  candidate_count: number;
  retrieval_sources: Record<string, RetrievalSource>;
  final_ranking_scores: Array<{ parent_asin: string; score: number }>;
  override_count: number;
  turn_count: number;
}

export interface TurnResponse {
  session_id: string;
  turn: number;
  message: string;
  ask_attribute: string | null;
  recommendations: ProductRecommendation[];
  debug: DebugSnapshot;
}

export interface MetricGroup {
  sample_count: number;
  hit_rate_at_10: number;
  mrr: number;
  mttc: number | null;
  efficiency: number;
  recommended_technical_score: number;
  scenario_metrics: Record<
    string,
    { sample_count: number; hit_rate_at_10: number; mrr: number; mttc: number }
  >;
  reported_token_usage: Record<string, number>;
}

export interface MetricsResponse {
  candidate: MetricGroup;
  baseline: MetricGroup;
  label: string;
}

export interface ChatEntry {
  id: string;
  role: "user" | "agent";
  content: string;
  turn: number;
  askAttribute?: string | null;
}
