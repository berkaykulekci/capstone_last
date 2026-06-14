import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from 'expo-router';

import { API_URL, useAuth } from '@/contexts/auth-context';

/* ── Design tokens (matching index.tsx) ── */
const C = {
  bg: '#0B0F16',
  surface: '#151A21',
  border: '#2B333F',
  text: '#EEF2F7',
  muted: '#9AA3AF',
  primary: '#10B7DF',
  danger: '#EF4444',
  amber: '#F5B51B',
  green: '#37C563',
  purple: '#A855F7',
  orange: '#F97316',
};

const RISK_COLORS: Record<string, string> = {
  High: C.danger,
  Moderate: C.amber,
  Low: C.green,
  'No data': '#455264',
};

const MODEL_COLORS: Record<string, string> = {
  mediapipe: C.primary,
  yolo: C.purple,
  rtm: C.orange,
};

const MODEL_LABELS: Record<string, string> = {
  mediapipe: 'MediaPipe',
  yolo: 'YOLO',
  rtm: 'RTMPose',
};

/* ── Types ── */
type StatisticsData = {
  total_athletes: number;
  total_analyses: number;
  risk_distribution: Record<string, number>;
  score_distribution: Record<string, number>;
  model_usage: Record<string, number>;
  sport_summary: {
    sport: string;
    analyses: number;
    avg_score: number | null;
    high: number;
    moderate: number;
    low: number;
  }[];
  score_timeline: { date: string; score: number; athlete: string; model: string }[];
  athlete_summaries: {
    id: string;
    name: string;
    sport: string | null;
    team: string | null;
    total_analyses: number;
    avg_score: number | null;
    latest_score: number | null;
    latest_risk: string | null;
    latest_model: string | null;
  }[];
};

/* ════════════════════════════════════════
   Utility components
   ════════════════════════════════════════ */

function KpiCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
}) {
  return (
    <View style={[kpiStyles.card, { borderLeftColor: accent }]}>
      <View style={[kpiStyles.iconWrap, { backgroundColor: accent + '22' }]}>
        <Ionicons name={icon} size={22} color={accent} />
      </View>
      <View style={kpiStyles.body}>
        <Text style={kpiStyles.value}>{value}</Text>
        <Text style={kpiStyles.label}>{label}</Text>
        {sub ? <Text style={kpiStyles.sub}>{sub}</Text> : null}
      </View>
    </View>
  );
}

const kpiStyles = StyleSheet.create({
  card: {
    flex: 1,
    minWidth: '47%',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.border,
    borderLeftWidth: 4,
    backgroundColor: C.surface,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: { flex: 1, gap: 2 },
  value: { color: C.text, fontSize: 28, fontWeight: '800', lineHeight: 32 },
  label: { color: C.muted, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  sub: { color: C.muted, fontSize: 11 },
});

/* ── Horizontal bar chart ── */
function BarChart({
  title,
  data,
  colorFn,
}: {
  title: string;
  data: { label: string; value: number; key: string }[];
  colorFn: (key: string) => string;
}) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <View style={chartStyles.card}>
      <Text style={chartStyles.title}>{title}</Text>
      {data.map((item) => (
        <View key={item.key} style={chartStyles.barRow}>
          <Text style={chartStyles.barLabel} numberOfLines={1}>{item.label}</Text>
          <View style={chartStyles.barTrack}>
            <View
              style={[
                chartStyles.barFill,
                { width: `${(item.value / max) * 100}%`, backgroundColor: colorFn(item.key) },
              ]}
            />
          </View>
          <Text style={chartStyles.barValue}>{item.value}</Text>
        </View>
      ))}
      {data.length === 0 && <Text style={chartStyles.empty}>Henüz analiz yok.</Text>}
    </View>
  );
}

const chartStyles = StyleSheet.create({
  card: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
    padding: 16,
    gap: 12,
  },
  title: { color: C.text, fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  barLabel: { color: C.muted, fontSize: 12, width: 80 },
  barTrack: { flex: 1, height: 10, borderRadius: 5, backgroundColor: '#1c2430', overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 5 },
  barValue: { color: C.text, fontSize: 12, fontWeight: '700', width: 28, textAlign: 'right' },
  empty: { color: C.muted, textAlign: 'center', paddingVertical: 12 },
});

/* ── Donut chart (pure RN view-based) ── */
function DonutLegend({
  data,
}: {
  data: { name: string; value: number; total: number }[];
}) {
  return (
    <View style={donutStyles.card}>
      <Text style={donutStyles.title}>Risk Dağılımı</Text>
      {data.length === 0 ? (
        <Text style={donutStyles.empty}>Henüz analiz yok.</Text>
      ) : (
        data.map((item) => {
          const pct = item.total > 0 ? Math.round((item.value / item.total) * 100) : 0;
          return (
            <View key={item.name} style={donutStyles.row}>
              <View style={[donutStyles.dot, { backgroundColor: RISK_COLORS[item.name] || '#455264' }]} />
              <Text style={donutStyles.name}>{item.name}</Text>
              <View style={donutStyles.trackWrap}>
                <View
                  style={[
                    donutStyles.fill,
                    { width: `${pct}%`, backgroundColor: RISK_COLORS[item.name] || '#455264' },
                  ]}
                />
              </View>
              <Text style={donutStyles.count}>{item.value}</Text>
              <Text style={donutStyles.pct}>{pct}%</Text>
            </View>
          );
        })
      )}
    </View>
  );
}

const donutStyles = StyleSheet.create({
  card: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
    padding: 16,
    gap: 12,
  },
  title: { color: C.text, fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },
  empty: { color: C.muted, textAlign: 'center', paddingVertical: 12 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  name: { color: C.muted, fontSize: 12, width: 68 },
  trackWrap: { flex: 1, height: 8, borderRadius: 4, backgroundColor: '#1c2430', overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 4 },
  count: { color: C.text, fontSize: 12, fontWeight: '700', width: 24, textAlign: 'right' },
  pct: { color: C.muted, fontSize: 11, width: 34, textAlign: 'right' },
});

/* ── Timeline sparkline (mini bar sparkline) ── */
function TimelineSparkline({
  data,
}: {
  data: { date: string; avg: number }[];
}) {
  if (data.length === 0) return null;
  const max = 19; // max possible LESS score
  return (
    <View style={sparkStyles.card}>
      <Text style={sparkStyles.title}>Zaman İçinde Ortalama Skor</Text>
      <View style={sparkStyles.bars}>
        {data.map((item, i) => (
          <View key={i} style={sparkStyles.col}>
            <Text style={sparkStyles.scoreLabel}>{item.avg}</Text>
            <View style={sparkStyles.track}>
              <View
                style={[sparkStyles.fill, { height: `${(item.avg / max) * 100}%` }]}
              />
            </View>
            <Text style={sparkStyles.dateLabel} numberOfLines={1}>
              {item.date.slice(5)}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const sparkStyles = StyleSheet.create({
  card: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
    padding: 16,
    gap: 12,
  },
  title: { color: C.text, fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },
  bars: { flexDirection: 'row', alignItems: 'flex-end', gap: 6, height: 120 },
  col: { flex: 1, alignItems: 'center', gap: 4, height: '100%', justifyContent: 'flex-end' },
  track: { width: '100%', height: 80, backgroundColor: '#1c2430', borderRadius: 4, overflow: 'hidden', justifyContent: 'flex-end' },
  fill: { width: '100%', backgroundColor: C.primary, borderRadius: 4 },
  scoreLabel: { color: C.primary, fontSize: 9, fontWeight: '700' },
  dateLabel: { color: C.muted, fontSize: 8, textAlign: 'center' },
});

/* ── Section card wrapper ── */
function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={sectionStyles.card}>
      <Text style={sectionStyles.title}>{title}</Text>
      {children}
    </View>
  );
}

const sectionStyles = StyleSheet.create({
  card: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
    padding: 16,
    gap: 10,
  },
  title: { color: C.text, fontSize: 14, fontWeight: '800', letterSpacing: 0.3, marginBottom: 4 },
});

/* ── Risk pill ── */
function RiskPill({ risk }: { risk: string | null }) {
  if (!risk) return <Text style={{ color: C.muted, fontSize: 12 }}>—</Text>;
  const color = RISK_COLORS[risk] || C.muted;
  return (
    <View style={{ borderRadius: 999, borderWidth: 1, borderColor: color + '55', backgroundColor: color + '22', paddingHorizontal: 8, paddingVertical: 2, alignSelf: 'flex-start' }}>
      <Text style={{ color, fontSize: 11, fontWeight: '700' }}>{risk}</Text>
    </View>
  );
}

/* ════════════════════════════════════════
   Main StatisticsScreen
   ════════════════════════════════════════ */
export default function StatisticsScreen() {
  const { token } = useAuth();
  const [data, setData] = useState<StatisticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError('');
      const res = await fetch(`${API_URL}/athletes/statistics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Veriler yüklenemedi.');
      const json: StatisticsData = await res.json();
      setData(json);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Bilinmeyen hata.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Reload every time screen comes into focus
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.primary} size="large" />
        <Text style={styles.loadingText}>İstatistikler yükleniyor...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Ionicons name="warning-outline" size={48} color={C.danger} />
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={load}>
          <Text style={styles.retryText}>Tekrar Dene</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!data) return null;

  /* ── Derived values ── */
  const totalWithScores = data.athlete_summaries.filter((a) => a.avg_score !== null);
  const overallAvg =
    totalWithScores.length > 0
      ? totalWithScores.reduce((s, a) => s + (a.avg_score ?? 0), 0) / totalWithScores.length
      : null;

  const highRisk = data.risk_distribution['High'] ?? 0;

  const riskTotal = Object.values(data.risk_distribution).reduce((s, v) => s + v, 0);
  const riskLegend = Object.entries(data.risk_distribution).map(([name, value]) => ({
    name,
    value,
    total: riskTotal,
  }));

  const scoreDistItems = Object.entries(data.score_distribution).map(([k, v]) => ({
    label: k,
    key: k,
    value: v,
  }));

  const modelItems = Object.entries(data.model_usage).map(([k, v]) => ({
    label: MODEL_LABELS[k] || k,
    key: k,
    value: v,
  }));

  // Timeline: group by date, average per date
  const timelineMap: Record<string, number[]> = {};
  for (const entry of data.score_timeline) {
    if (!timelineMap[entry.date]) timelineMap[entry.date] = [];
    timelineMap[entry.date].push(entry.score);
  }
  const timelineData = Object.entries(timelineMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-14) // last 14 data points max
    .map(([date, scores]) => ({
      date,
      avg: Math.round((scores.reduce((s, v) => s + v, 0) / scores.length) * 10) / 10,
    }));

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>İstatistikler</Text>
          <Text style={styles.subtitle}>Tüm sporcu analiz verileri</Text>
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={load}>
          <Ionicons name="refresh-outline" size={20} color={C.primary} />
        </TouchableOpacity>
      </View>

      {/* KPI Grid */}
      <View style={styles.kpiGrid}>
        <KpiCard
          icon="people-outline"
          label="Toplam Sporcu"
          value={data.total_athletes}
          accent={C.primary}
        />
        <KpiCard
          icon="flask-outline"
          label="Toplam Analiz"
          value={data.total_analyses}
          accent={C.purple}
        />
        <KpiCard
          icon="pulse-outline"
          label="Ort. Skor"
          value={overallAvg !== null ? overallAvg.toFixed(1) : '—'}
          sub="/ 19 puan"
          accent={C.green}
        />
        <KpiCard
          icon="warning-outline"
          label="Yüksek Risk"
          value={highRisk}
          accent={C.danger}
        />
      </View>

      {/* Risk Distribution */}
      <DonutLegend data={riskLegend} />

      {/* Score Distribution */}
      <BarChart
        title="Skor Dağılımı"
        data={scoreDistItems}
        colorFn={(key) => {
          const map: Record<string, string> = {
            '0-4': C.danger,
            '5-9': C.amber,
            '10-14': C.primary,
            '15-19': C.green,
          };
          return map[key] || C.primary;
        }}
      />

      {/* Model Usage */}
      <BarChart
        title="Model Kullanımı"
        data={modelItems}
        colorFn={(key) => MODEL_COLORS[key] || C.primary}
      />

      {/* Score Timeline */}
      {timelineData.length > 0 && <TimelineSparkline data={timelineData} />}

      {/* Sport Summary */}
      {data.sport_summary.length > 0 && (
        <SectionCard title="Spora Göre Dağılım">
          {/* Header row */}
          <View style={tableStyles.headerRow}>
            <Text style={[tableStyles.cell, tableStyles.headerCell, { flex: 2 }]}>Spor</Text>
            <Text style={[tableStyles.cell, tableStyles.headerCell]}>Analiz</Text>
            <Text style={[tableStyles.cell, tableStyles.headerCell]}>Ort.</Text>
            <Text style={[tableStyles.cell, tableStyles.headerCell]}>Y</Text>
            <Text style={[tableStyles.cell, tableStyles.headerCell]}>O</Text>
            <Text style={[tableStyles.cell, tableStyles.headerCell]}>D</Text>
          </View>
          {data.sport_summary.map((row) => (
            <View key={row.sport} style={tableStyles.row}>
              <Text style={[tableStyles.cell, tableStyles.nameCell, { flex: 2 }]} numberOfLines={1}>
                {row.sport}
              </Text>
              <Text style={tableStyles.cell}>{row.analyses}</Text>
              <Text style={tableStyles.cell}>{row.avg_score ?? '—'}</Text>
              <Text style={[tableStyles.cell, { color: C.danger }]}>{row.high}</Text>
              <Text style={[tableStyles.cell, { color: C.amber }]}>{row.moderate}</Text>
              <Text style={[tableStyles.cell, { color: C.green }]}>{row.low}</Text>
            </View>
          ))}
          <Text style={tableStyles.legend}>Y=Yüksek  O=Orta  D=Düşük</Text>
        </SectionCard>
      )}

      {/* Athlete Summary */}
      {data.athlete_summaries.length > 0 && (
        <SectionCard title="Sporcu Özeti">
          {data.athlete_summaries.map((a, i) => (
            <View
              key={a.id}
              style={[athleteStyles.row, i > 0 && athleteStyles.rowBorder]}
            >
              <View style={athleteStyles.avatar}>
                <Text style={athleteStyles.avatarText}>
                  {(a.name || 'A').charAt(0).toUpperCase()}
                </Text>
              </View>
              <View style={athleteStyles.info}>
                <Text style={athleteStyles.name}>{a.name}</Text>
                <Text style={athleteStyles.meta} numberOfLines={1}>
                  {a.sport || '—'}{a.team ? ` · ${a.team}` : ''}
                </Text>
                <View style={athleteStyles.tags}>
                  <RiskPill risk={a.latest_risk} />
                  {a.latest_model ? (
                    <View style={athleteStyles.modelTag}>
                      <Text style={athleteStyles.modelTagText}>
                        {MODEL_LABELS[a.latest_model] || a.latest_model}
                      </Text>
                    </View>
                  ) : null}
                </View>
              </View>
              <View style={athleteStyles.scores}>
                <Text style={athleteStyles.scoreVal}>
                  {a.latest_score !== null && a.latest_score !== undefined ? a.latest_score : '—'}
                </Text>
                <Text style={athleteStyles.scoreSub}>son</Text>
                <Text style={athleteStyles.scoreVal}>
                  {a.avg_score !== null ? a.avg_score : '—'}
                </Text>
                <Text style={athleteStyles.scoreSub}>ort.</Text>
              </View>
            </View>
          ))}
        </SectionCard>
      )}

      {/* Empty state */}
      {data.total_athletes === 0 && (
        <View style={styles.emptyState}>
          <Ionicons name="bar-chart-outline" size={56} color={C.border} />
          <Text style={styles.emptyTitle}>Henüz veri yok</Text>
          <Text style={styles.emptyText}>
            Sporcu ekleyin ve analiz çalıştırın, istatistikler burada görünür.
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

/* ── Table styles ── */
const tableStyles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderColor: C.border,
    gap: 4,
  },
  row: {
    flexDirection: 'row',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderColor: '#1c2430',
    gap: 4,
  },
  cell: { flex: 1, color: C.muted, fontSize: 12, textAlign: 'center' },
  headerCell: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  nameCell: { color: C.text, fontWeight: '700', textAlign: 'left' },
  legend: { color: C.muted, fontSize: 10, marginTop: 4 },
});

/* ── Athlete summary row styles ── */
const athleteStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    gap: 12,
  },
  rowBorder: {
    borderTopWidth: 1,
    borderColor: '#1c2430',
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: '#103140',
    borderWidth: 1,
    borderColor: '#15506B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { color: C.primary, fontWeight: '800', fontSize: 16 },
  info: { flex: 1, gap: 4 },
  name: { color: C.text, fontWeight: '800', fontSize: 14 },
  meta: { color: C.muted, fontSize: 12 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2 },
  modelTag: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#15506B',
    backgroundColor: '#0c3144',
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  modelTagText: { color: C.primary, fontSize: 11, fontWeight: '700' },
  scores: { alignItems: 'center', gap: 2 },
  scoreVal: { color: C.text, fontWeight: '800', fontSize: 16, textAlign: 'center' },
  scoreSub: { color: C.muted, fontSize: 10, textAlign: 'center' },
});

/* ── Screen-level styles ── */
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  content: { padding: 20, paddingTop: 62, paddingBottom: 48, gap: 16 },
  center: { flex: 1, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32 },
  loadingText: { color: C.muted, fontSize: 14 },
  errorText: { color: C.danger, textAlign: 'center', fontSize: 14 },
  retryBtn: { height: 42, paddingHorizontal: 24, borderRadius: 8, backgroundColor: '#108DB2', justifyContent: 'center' },
  retryText: { color: '#fff', fontWeight: '800' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { color: C.text, fontSize: 28, fontWeight: '800' },
  subtitle: { color: C.muted, marginTop: 4 },
  refreshBtn: {
    width: 42,
    height: 42,
    borderRadius: 8,
    backgroundColor: '#103140',
    borderWidth: 1,
    borderColor: '#15506B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  kpiGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  emptyState: { alignItems: 'center', gap: 12, paddingVertical: 40 },
  emptyTitle: { color: C.text, fontSize: 18, fontWeight: '800' },
  emptyText: { color: C.muted, textAlign: 'center', lineHeight: 20 },
});
