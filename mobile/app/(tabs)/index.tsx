import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Directory, File as ExpoFile } from 'expo-file-system';

import { API_URL, useAuth } from '@/contexts/auth-context';

const POSE_MODELS_KEY = 'sportsmd_pose_models';
const TEST_SIDE_KEY   = 'sportsmd_test_side';

type PoseModel = 'mediapipe' | 'yolo' | 'rtm';
type TestSide  = 'right' | 'left';

const MODEL_OPTIONS: { id: PoseModel; label: string; note: string }[] = [
  { id: 'mediapipe', label: 'MediaPipe', note: 'Auto-detects side via Z-coord. All 17 items exact.' },
  { id: 'yolo',      label: 'YOLO Pose', note: 'No heel/toe → M4/M9/M10 approximated. Items flagged in CSV.' },
  { id: 'rtm',       label: 'RTMPose',   note: 'Heel + toe present → all 17 items exact, no approximations.' },
];

type Analysis = {
  id: string;
  risk?: string;
  status?: string;
  total_score?: number;
  csv_url?: string | null;
  side_output_url?: string | null;
  front_output_url?: string | null;
  pose_model?: string | null;
  created_at?: string;
};

type Athlete = {
  id: string;
  name: string;
  sport?: string;
  team?: string;
  latest_analysis?: Analysis | null;
  analyses?: Analysis[];
};

type PickedVideo = {
  uri: string;
  name: string;
  type: string;
};

const VIDEO_EXTENSIONS = ['mp4', 'mov', 'm4v', 'avi', 'qt'];
const VIDEO_MIME_BY_EXTENSION: Record<string, string> = {
  avi: 'video/x-msvideo',
  m4v: 'video/x-m4v',
  mov: 'video/quicktime',
  mp4: 'video/mp4',
  qt: 'video/quicktime',
};

const C = {
  bg: '#0B0F16',
  surface: '#151A21',
  border: '#2B333F',
  text: '#EEF2F7',
  muted: '#9AA3AF',
  primary: '#10B7DF',
  button: '#108DB2',
  danger: '#EF4444',
  amber: '#F5B51B',
  green: '#37C563',
};

function apiUrl(path?: string | null) {
  if (!path) return '';
  return path.startsWith('http') ? path : `${API_URL}${path}`;
}

function extensionFromName(value: string) {
  const cleanValue = value.split('?')[0] || '';
  const extension = cleanValue.includes('.') ? cleanValue.split('.').pop() : '';
  return (extension || '').toLowerCase();
}

function mimeForVideo(name: string, mimeType?: string) {
  const extension = extensionFromName(name);
  if (mimeType && mimeType !== 'application/octet-stream') return mimeType;
  return VIDEO_MIME_BY_EXTENSION[extension] || 'video/mp4';
}

function normalisePickedVideo(file: unknown): PickedVideo | null {
  const picked = file as { uri?: string; name?: string; type?: string };
  if (!picked?.uri) return null;
  const name = picked.name || decodeURIComponent(picked.uri.split('/').pop() || 'video.mp4');
  return { uri: picked.uri, name, type: mimeForVideo(name, picked.type) };
}

function isSupportedVideo(file: PickedVideo) {
  const extension = extensionFromName(file.name || file.uri);
  return VIDEO_EXTENSIONS.includes(extension) || file.type.startsWith('video/');
}

function uploadPart(file: PickedVideo) {
  return {
    uri: file.uri,
    name: file.name || file.uri.split('/').pop() || 'video.mp4',
    type: mimeForVideo(file.name || file.uri, file.type),
  };
}

function formatDate(value?: string) {
  if (!value) return '';
  return new Date(value).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function safeFileName(value: string) {
  return value
    .replace(/[^a-zA-Z0-9._-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    || `sportsmd_output_${Date.now()}`;
}

function outputFileName(path: string, fallbackName: string) {
  const lastPart = decodeURIComponent((path.split('?')[0] || '').split('/').pop() || '');
  return safeFileName(lastPart || fallbackName);
}

function isAuthError(status: number, detail?: string) {
  return status === 401 || (detail || '').toLowerCase().includes('validate credentials');
}

function modelLabel(model?: string | null) {
  if (model === 'yolo') return 'YOLO';
  if (model === 'rtm') return 'RTMPose';
  return 'MediaPipe';
}

// Group analyses submitted within the same minute into comparison batches
function groupAnalyses(analyses: Analysis[]): Analysis[][] {
  if (!analyses.length) return [];
  const asc = [...analyses].reverse();
  const minuteKey = (a: Analysis) => (a.created_at || '').slice(0, 16);
  const groups: Analysis[][] = [];
  let current: Analysis[] = [asc[0]];
  for (let i = 1; i < asc.length; i++) {
    if (minuteKey(asc[i]) === minuteKey(current[0])) {
      current.push(asc[i]);
    } else {
      groups.push(current);
      current = [asc[i]];
    }
  }
  groups.push(current);
  return groups.reverse();
}

export default function HomeScreen() {
  const { token, logout } = useAuth();
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [selectedAthlete, setSelectedAthlete] = useState<Athlete | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [name, setName] = useState('');
  const [sport, setSport] = useState('');
  const [team, setTeam] = useState('');
  const [poseModels, setPoseModels] = useState<PoseModel[]>(['mediapipe']);
  const [testSide, setTestSide] = useState<TestSide>('right');

  const needsTestSide = poseModels.some((m) => m === 'yolo' || m === 'rtm');

  const stats = useMemo(() => {
    const high = athletes.filter((item) => item.latest_analysis?.risk === 'High').length;
    const moderate = athletes.filter((item) => item.latest_analysis?.risk === 'Moderate').length;
    return { high, moderate, low: athletes.length - high - moderate };
  }, [athletes]);

  const loadAthletes = useCallback(async () => {
    if (!token) return;
    const res = await fetch(`${API_URL}/athletes`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const body = await res.json();
      if (isAuthError(res.status, body.detail)) { await logout(); return; }
      throw new Error(body.detail || 'Could not load athletes');
    }
    const items: Athlete[] = await res.json();
    setAthletes(items);
    setSelectedAthlete((current) => {
      if (!current) return null;
      return items.find((item) => item.id === current.id) || current;
    });
  }, [logout, token]);

  useEffect(() => {
    async function init() {
      const [storedModels, storedSide] = await Promise.all([
        AsyncStorage.getItem(POSE_MODELS_KEY),
        AsyncStorage.getItem(TEST_SIDE_KEY),
      ]);
      if (storedModels) {
        try {
          const parsed: PoseModel[] = JSON.parse(storedModels);
          if (Array.isArray(parsed) && parsed.length > 0) setPoseModels(parsed);
        } catch { /* ignore */ }
      }
      if (storedSide === 'left' || storedSide === 'right') setTestSide(storedSide);
      await loadAthletes().catch((err) => Alert.alert('Error', err.message));
      setLoading(false);
    }
    init();
  }, [loadAthletes]);

  async function togglePoseModel(model: PoseModel) {
    let next: PoseModel[];
    if (poseModels.includes(model)) {
      if (poseModels.length === 1) return; // keep at least one
      next = poseModels.filter((m) => m !== model);
    } else {
      next = [...poseModels, model];
    }
    setPoseModels(next);
    await AsyncStorage.setItem(POSE_MODELS_KEY, JSON.stringify(next));
  }

  async function saveTestSide(value: TestSide) {
    setTestSide(value);
    await AsyncStorage.setItem(TEST_SIDE_KEY, value);
  }

  async function refresh() {
    setRefreshing(true);
    await loadAthletes().catch((err) => Alert.alert('Error', err.message));
    setRefreshing(false);
  }

  async function createAthlete() {
    if (!name.trim()) { Alert.alert('Missing name', 'Please enter an athlete name.'); return; }
    const res = await fetch(`${API_URL}/athletes`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, sport, team }),
    });
    if (!res.ok) {
      const body = await res.json();
      if (isAuthError(res.status, body.detail)) { await logout(); return; }
      Alert.alert('Error', body.detail || 'Athlete could not be created');
      return;
    }
    const created: Athlete = await res.json();
    setName(''); setSport(''); setTeam('');
    setModalVisible(false);
    setSelectedAthlete(created);
    await loadAthletes();
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.primary} size="large" />
      </View>
    );
  }

  if (selectedAthlete) {
    return (
      <AthleteDetail
        athlete={selectedAthlete}
        token={token}
        poseModels={poseModels}
        testSide={testSide}
        onBack={() => setSelectedAthlete(null)}
        onSessionExpired={logout}
        onRefresh={loadAthletes}
      />
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Athlete Dashboard</Text>
          <Text style={styles.subtitle}>{athletes.length} athletes assigned</Text>
        </View>
        <View style={styles.headerActions}>
          <TouchableOpacity style={styles.iconButton} onPress={() => setSettingsVisible(true)}>
            <Ionicons name="settings-outline" size={22} color={C.text} />
          </TouchableOpacity>
          <TouchableOpacity style={styles.iconButton} onPress={logout}>
            <Ionicons name="log-out-outline" size={22} color={C.text} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Active model badge row */}
      <View style={styles.modelBadgeRow}>
        {poseModels.map((m) => (
          <View key={m} style={styles.modelBadge}>
            <Text style={styles.modelBadgeText}>
              {modelLabel(m)}{(m === 'yolo' || m === 'rtm') ? ` · ${testSide}` : ''}
            </Text>
          </View>
        ))}
      </View>

      <View style={styles.stats}>
        <Stat label="Total" value={athletes.length} />
        <Stat label="High" value={stats.high} tone="red" />
        <Stat label="Moderate" value={stats.moderate} tone="amber" />
        <Stat label="Low / No Data" value={stats.low} tone="green" />
      </View>

      <TouchableOpacity style={styles.addButton} onPress={() => setModalVisible(true)}>
        <Ionicons name="add" size={20} color="#fff" />
        <Text style={styles.addButtonText}>Add Athlete</Text>
      </TouchableOpacity>

      <FlatList
        data={athletes}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        ListEmptyComponent={<Text style={styles.empty}>No athletes yet.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => setSelectedAthlete(item)} activeOpacity={0.78}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{item.name.charAt(0).toUpperCase()}</Text>
            </View>
            <View style={styles.rowCopy}>
              <Text style={styles.rowTitle}>{item.name}</Text>
              <Text style={styles.rowMeta}>{item.sport || '-'} · {item.team || '-'}</Text>
            </View>
            <Text style={styles.pill}>{item.latest_analysis?.risk || 'No data'}</Text>
            <Ionicons name="chevron-forward" size={18} color={C.muted} />
          </TouchableOpacity>
        )}
      />

      {/* Add Athlete Modal */}
      <Modal visible={modalVisible} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modal}>
            <Text style={styles.modalTitle}>Add New Athlete</Text>
            <TextInput style={styles.input} placeholder="Full name" placeholderTextColor={C.muted} value={name} onChangeText={setName} />
            <TextInput style={styles.input} placeholder="Sport" placeholderTextColor={C.muted} value={sport} onChangeText={setSport} />
            <TextInput style={styles.input} placeholder="Team" placeholderTextColor={C.muted} value={team} onChangeText={setTeam} />
            <View style={styles.modalActions}>
              <TouchableOpacity style={styles.secondaryButton} onPress={() => setModalVisible(false)}>
                <Text style={styles.secondaryText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.primaryButton} onPress={createAthlete}>
                <Text style={styles.primaryText}>Create Athlete</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Analysis Settings Modal */}
      <Modal visible={settingsVisible} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <ScrollView contentContainerStyle={styles.modalScrollContent} showsVerticalScrollIndicator={false}>
            <View style={styles.modal}>
              <Text style={styles.modalTitle}>Analysis Settings</Text>
              <Text style={styles.settingLabel}>Pose Models</Text>
              <Text style={styles.settingNote}>Select one or more models to run in a single evaluation.</Text>

              {MODEL_OPTIONS.map(({ id, label, note }) => {
                const checked = poseModels.includes(id);
                return (
                  <TouchableOpacity
                    key={id}
                    style={[styles.checkRow, checked && styles.checkRowActive]}
                    onPress={() => togglePoseModel(id)}
                    activeOpacity={0.75}
                  >
                    <View style={[styles.checkbox, checked && styles.checkboxActive]}>
                      {checked && <Text style={styles.checkmark}>✓</Text>}
                    </View>
                    <View style={styles.checkContent}>
                      <Text style={[styles.checkLabel, checked && styles.checkLabelActive]}>{label}</Text>
                      <Text style={styles.checkNote}>{note}</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}

              {poseModels.length > 1 && (
                <View style={styles.multiModelNote}>
                  <Text style={styles.multiModelNoteText}>
                    {poseModels.length} models selected — results will be shown as a comparison.
                  </Text>
                </View>
              )}

              {needsTestSide && (
                <>
                  <Text style={[styles.settingLabel, { marginTop: 18 }]}>Test Leg (side camera)</Text>
                  <View style={styles.toggleRow}>
                    <TouchableOpacity
                      style={[styles.toggleBtn, testSide === 'right' && styles.toggleBtnActive]}
                      onPress={() => saveTestSide('right')}
                    >
                      <Text style={[styles.toggleText, testSide === 'right' && styles.toggleTextActive]}>Right</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.toggleBtn, testSide === 'left' && styles.toggleBtnActive]}
                      onPress={() => saveTestSide('left')}
                    >
                      <Text style={[styles.toggleText, testSide === 'left' && styles.toggleTextActive]}>Left</Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}

              <View style={[styles.modalActions, { marginTop: 20 }]}>
                <TouchableOpacity style={styles.primaryButton} onPress={() => setSettingsVisible(false)}>
                  <Text style={styles.primaryText}>Done</Text>
                </TouchableOpacity>
              </View>
            </View>
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

function AthleteDetail({
  athlete,
  token,
  poseModels,
  testSide,
  onBack,
  onSessionExpired,
  onRefresh,
}: {
  athlete: Athlete;
  token: string | null;
  poseModels: PoseModel[];
  testSide: TestSide;
  onBack: () => void;
  onSessionExpired: () => Promise<void>;
  onRefresh: () => Promise<void>;
}) {
  const [sideFile, setSideFile] = useState<PickedVideo | null>(null);
  const [frontFile, setFrontFile] = useState<PickedVideo | null>(null);
  const [busy, setBusy] = useState(false);
  const [downloadingOutput, setDownloadingOutput] = useState<string | null>(null);
  const analyses = athlete.analyses || [];
  const latest = athlete.latest_analysis;
  const groups = groupAnalyses(analyses);

  async function pickVideo(target: 'side' | 'front') {
    try {
      const picked = await ExpoFile.pickFileAsync();
      const file = Array.isArray(picked) ? picked[0] : picked;
      const video = normalisePickedVideo(file);
      if (!video) { Alert.alert('Video could not be selected', 'Please choose the video again from Files.'); return; }
      if (!isSupportedVideo(video)) { Alert.alert('Unsupported format', 'Please choose an MP4, MOV, M4V, or AVI video.'); return; }
      if (target === 'side') setSideFile(video);
      else setFrontFile(video);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '';
      if (!message.toLowerCase().includes('cancel')) Alert.alert('Error', message || 'Video could not be selected');
    }
  }

  async function analyse() {
    if (!sideFile || !frontFile) {
      Alert.alert('Missing videos', 'Please select both side and front videos.');
      return;
    }
    setBusy(true);
    const form = new FormData();
    form.append('side_video', uploadPart(sideFile) as unknown as Blob);
    form.append('front_video', uploadPart(frontFile) as unknown as Blob);
    form.append('pose_models', poseModels.join(','));
    form.append('test_side', testSide);

    try {
      const res = await fetch(`${API_URL}/athletes/${athlete.id}/analyse`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const body = await res.json();
      if (!res.ok && isAuthError(res.status, body.detail)) { await onSessionExpired(); return; }
      if (!res.ok) throw new Error(body.detail || 'Analysis failed');
      setSideFile(null);
      setFrontFile(null);
      await onRefresh();
      const count = Array.isArray(body) ? body.length : 1;
      Alert.alert('Analysis complete', count > 1 ? `${count} model results are ready.` : 'The athlete analysis is ready.');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Analysis failed';
      Alert.alert('Error', message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteAnalysis(analysisId: string) {
    Alert.alert('Delete analysis', 'Are you sure you want to delete this analysis?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          setBusy(true);
          try {
            const res = await fetch(`${API_URL}/athletes/${athlete.id}/analyses/${analysisId}`, {
              method: 'DELETE',
              headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) {
              const body = await res.json();
              if (isAuthError(res.status, body.detail)) { await onSessionExpired(); return; }
              throw new Error(body.detail || 'Analysis deletion failed');
            }
            await onRefresh();
          } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Analysis deletion failed';
            Alert.alert('Error', message);
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function downloadOutput(path: string, fallbackName: string, title: string) {
    const fileKey = `${title}-${path}`;
    setDownloadingOutput(fileKey);
    try {
      const directory = await Directory.pickDirectoryAsync();
      const filename = outputFileName(path, fallbackName);
      await ExpoFile.downloadFileAsync(apiUrl(path), directory, {
        idempotent: true,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      Alert.alert('Download complete', `${title} saved as ${filename}.`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '';
      if (!message.toLowerCase().includes('cancel')) Alert.alert('Download failed', message || 'Output could not be downloaded');
    } finally {
      setDownloadingOutput(null);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.detailContent}>
      <View style={styles.detailHeader}>
        <TouchableOpacity style={styles.backIconButton} onPress={onBack}>
          <Ionicons name="arrow-back" size={22} color={C.primary} />
        </TouchableOpacity>
        <View style={styles.detailHeaderCopy}>
          <Text style={styles.title}>{athlete.name}</Text>
          <Text style={styles.subtitle}>{athlete.sport || '-'} · {athlete.team || '-'}</Text>
        </View>
      </View>

      <View style={styles.profileCard}>
        <View style={styles.profileTopRow}>
          <View style={styles.avatarLarge}>
            <Text style={styles.avatarLargeText}>{athlete.name.charAt(0).toUpperCase()}</Text>
          </View>
          <View style={styles.profileStats}>
            <Text style={styles.profileLabel}>Latest Score</Text>
            <Text style={styles.profileValue}>{latest?.total_score ?? '-'}</Text>
          </View>
          <View style={styles.profileStats}>
            <Text style={styles.profileLabel}>Analyses</Text>
            <Text style={styles.profileValue}>{analyses.length}</Text>
          </View>
        </View>
        <View style={styles.athleteIdBox}>
          <Text style={styles.profileLabel}>Athlete ID</Text>
          <Text style={styles.athleteIdText}>{athlete.id}</Text>
        </View>
      </View>

      <View style={styles.uploadPanel}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Upload Video</Text>
          <View style={styles.activeBadgesRow}>
            {poseModels.map((m) => (
              <View key={m} style={styles.modelBadge}>
                <Text style={styles.modelBadgeText}>{modelLabel(m)}</Text>
              </View>
            ))}
          </View>
        </View>

        <UploadButton label="Side view (sagittal)" fileName={sideFile?.name} onPress={() => pickVideo('side')} />
        <UploadButton label="Front view (frontal)" fileName={frontFile?.name} onPress={() => pickVideo('front')} />

        {poseModels.length > 1 && (
          <View style={styles.multiRunNote}>
            <Text style={styles.multiRunNoteText}>
              Will run {poseModels.length} models — {poseModels.map(modelLabel).join(', ')}
            </Text>
          </View>
        )}

        <TouchableOpacity style={[styles.analyseButton, busy && styles.disabledButton]} onPress={analyse} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" /> : <Ionicons name="cloud-upload-outline" size={20} color="#fff" />}
          <Text style={styles.primaryText}>{busy ? 'Analysing...' : 'Upload & Analyse'}</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.uploadPanel}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Analysis History</Text>
          <Text style={styles.historyCount}>{busy ? '...' : analyses.length}</Text>
        </View>

        {analyses.length === 0 ? (
          <Text style={styles.emptyInline}>No analyses yet.</Text>
        ) : (
          groups.map((group, groupIdx) =>
            group.length === 1 ? (
              <AnalysisRow
                key={group[0].id}
                analysis={group[0]}
                athleteId={athlete.id}
                token={token}
                downloadingOutput={downloadingOutput}
                busy={busy}
                onDelete={deleteAnalysis}
                onDownload={downloadOutput}
              />
            ) : (
              <View key={groupIdx} style={styles.comparisonGroup}>
                <Text style={styles.comparisonGroupLabel}>
                  Comparison · {formatDate(group[0].created_at)}
                </Text>
                {group.map((analysis) => (
                  <AnalysisRow
                    key={analysis.id}
                    analysis={analysis}
                    athleteId={athlete.id}
                    token={token}
                    downloadingOutput={downloadingOutput}
                    busy={busy}
                    onDelete={deleteAnalysis}
                    onDownload={downloadOutput}
                    compact
                  />
                ))}
              </View>
            )
          )
        )}
      </View>
    </ScrollView>
  );
}

function AnalysisRow({
  analysis,
  downloadingOutput,
  busy,
  onDelete,
  onDownload,
  compact,
}: {
  analysis: Analysis;
  athleteId: string;
  token: string | null;
  downloadingOutput: string | null;
  busy: boolean;
  onDelete: (id: string) => void;
  onDownload: (path: string, fallback: string, title: string) => void;
  compact?: boolean;
}) {
  return (
    <View style={[styles.analysisCard, compact && styles.analysisCardCompact]}>
      <View style={styles.analysisTopRow}>
        <View style={styles.analysisBadges}>
          <View style={styles.modelPill}>
            <Text style={styles.modelPillText}>{modelLabel(analysis.pose_model)}</Text>
          </View>
          <Text style={styles.pill}>{analysis.risk || 'No data'}</Text>
        </View>
        <Text style={styles.analysisScore}>{analysis.total_score ?? '-'} puan</Text>
      </View>
      {!compact && (
        <Text style={styles.analysisMeta}>{formatDate(analysis.created_at)}</Text>
      )}
      <View style={styles.analysisActions}>
        {analysis.csv_url && (
          <TouchableOpacity
            style={styles.outputButton}
            onPress={() => onDownload(analysis.csv_url!, `${analysis.id}_less.csv`, 'CSV report')}
            disabled={downloadingOutput === `CSV report-${analysis.csv_url}`}
          >
            {downloadingOutput === `CSV report-${analysis.csv_url}` && <ActivityIndicator color={C.primary} size="small" />}
            <Text style={styles.outputButtonText}>CSV</Text>
          </TouchableOpacity>
        )}
        {analysis.side_output_url && (
          <TouchableOpacity
            style={styles.outputButton}
            onPress={() => onDownload(analysis.side_output_url!, `${analysis.id}_side.mp4`, 'Side video')}
            disabled={downloadingOutput === `Side video-${analysis.side_output_url}`}
          >
            {downloadingOutput === `Side video-${analysis.side_output_url}` && <ActivityIndicator color={C.primary} size="small" />}
            <Text style={styles.outputButtonText}>Side</Text>
          </TouchableOpacity>
        )}
        {analysis.front_output_url && (
          <TouchableOpacity
            style={styles.outputButton}
            onPress={() => onDownload(analysis.front_output_url!, `${analysis.id}_front.mp4`, 'Front video')}
            disabled={downloadingOutput === `Front video-${analysis.front_output_url}`}
          >
            {downloadingOutput === `Front video-${analysis.front_output_url}` && <ActivityIndicator color={C.primary} size="small" />}
            <Text style={styles.outputButtonText}>Front</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity style={styles.deleteButton} onPress={() => onDelete(analysis.id)} disabled={busy}>
          <Ionicons name="trash-outline" size={16} color="#ff6b6b" />
        </TouchableOpacity>
      </View>
    </View>
  );
}

function UploadButton({ label, fileName, onPress }: { label: string; fileName?: string; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.uploadBox} onPress={onPress} activeOpacity={0.78}>
      <Ionicons name="videocam-outline" size={24} color={C.primary} />
      <View style={styles.uploadCopy}>
        <Text style={styles.uploadLabel}>{label}</Text>
        <Text style={styles.uploadMeta} numberOfLines={1}>{fileName || 'MP4, MOV, AVI'}</Text>
      </View>
      <Ionicons name="add-circle-outline" size={22} color={C.muted} />
    </TouchableOpacity>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: 'red' | 'amber' | 'green' }) {
  return (
    <View style={[styles.stat, tone === 'red' && styles.red, tone === 'amber' && styles.amber, tone === 'green' && styles.green]}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg, padding: 20, paddingTop: 62 },
  detailContent: { gap: 14, paddingBottom: 48 },
  center: { flex: 1, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { color: C.text, fontSize: 28, fontWeight: '800' },
  subtitle: { color: C.muted, marginTop: 4 },
  iconButton: { width: 42, height: 42, borderRadius: 8, backgroundColor: '#1F2740', alignItems: 'center', justifyContent: 'center' },
  stats: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginVertical: 22 },
  stat: { width: '48%', borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.surface, padding: 16 },
  red: { borderLeftColor: C.danger, borderLeftWidth: 3 },
  amber: { borderLeftColor: C.amber, borderLeftWidth: 3 },
  green: { borderLeftColor: C.green, borderLeftWidth: 3 },
  statValue: { color: C.text, fontSize: 28, fontWeight: '800' },
  statLabel: { color: C.muted, marginTop: 4 },
  addButton: { height: 46, borderRadius: 8, backgroundColor: C.button, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, marginBottom: 14 },
  addButtonText: { color: '#fff', fontWeight: '800' },
  list: { gap: 10, paddingBottom: 40 },
  row: { minHeight: 76, borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.surface, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 44, height: 44, borderRadius: 10, backgroundColor: '#103140', borderWidth: 1, borderColor: '#15506B', alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: C.primary, fontWeight: '800' },
  rowCopy: { flex: 1 },
  rowTitle: { color: C.text, fontWeight: '800' },
  rowMeta: { color: C.muted, marginTop: 3 },
  pill: { color: C.muted, borderColor: C.border, borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4, overflow: 'hidden' },
  empty: { color: C.muted, textAlign: 'center', marginTop: 60 },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,.55)', alignItems: 'center', justifyContent: 'center', padding: 20 },
  modalScrollContent: { flexGrow: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  modal: { width: '100%', borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.surface, padding: 22, gap: 12 },
  headerActions: { flexDirection: 'row', gap: 8 },
  modelBadgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8, marginBottom: 4 },
  modelBadge: { alignSelf: 'flex-start', backgroundColor: '#103140', borderRadius: 999, borderWidth: 1, borderColor: '#15506B', paddingHorizontal: 10, paddingVertical: 3 },
  modelBadgeText: { color: C.primary, fontSize: 11, fontWeight: '700' },
  activeBadgesRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  detailHeader: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  backIconButton: { width: 42, height: 42, borderRadius: 8, borderWidth: 1, borderColor: '#15506B', backgroundColor: '#103140', alignItems: 'center', justifyContent: 'center' },
  detailHeaderCopy: { flex: 1 },
  profileCard: { borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.surface, padding: 16, gap: 14 },
  profileTopRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatarLarge: { width: 64, height: 64, borderRadius: 16, backgroundColor: '#103140', borderWidth: 1, borderColor: '#15506B', alignItems: 'center', justifyContent: 'center' },
  avatarLargeText: { color: C.primary, fontSize: 24, fontWeight: '800' },
  profileStats: { flex: 1, borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: '#0f141b', padding: 12 },
  profileLabel: { color: C.muted, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.6 },
  profileValue: { color: C.text, fontSize: 24, fontWeight: '800', marginTop: 4 },
  athleteIdBox: { borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: '#0D1219', padding: 12 },
  athleteIdText: { color: C.primary, fontWeight: '800', marginTop: 4 },
  uploadPanel: { borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.surface, padding: 16, gap: 12 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 10 },
  sectionTitle: { color: C.text, fontSize: 18, fontWeight: '800' },
  uploadBox: { minHeight: 76, borderRadius: 8, borderWidth: 1, borderStyle: 'dashed', borderColor: '#394250', backgroundColor: '#0f141b', paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', gap: 12 },
  uploadCopy: { flex: 1 },
  uploadLabel: { color: C.text, fontWeight: '800' },
  uploadMeta: { color: C.muted, marginTop: 3 },
  multiRunNote: { backgroundColor: '#0a2533', borderRadius: 6, borderWidth: 1, borderColor: '#15506b', padding: 8 },
  multiRunNoteText: { color: C.primary, fontSize: 12 },
  analyseButton: { minHeight: 46, borderRadius: 8, backgroundColor: C.button, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 },
  disabledButton: { opacity: 0.7 },
  historyCount: { minWidth: 28, borderRadius: 999, overflow: 'hidden', backgroundColor: '#1F2740', color: C.muted, textAlign: 'center', paddingHorizontal: 8, paddingVertical: 3, fontWeight: '800' },
  emptyInline: { color: C.muted, textAlign: 'center', paddingVertical: 24 },
  comparisonGroup: { gap: 6, marginBottom: 2 },
  comparisonGroupLabel: { color: C.primary, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.6, paddingVertical: 4 },
  analysisCard: { borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: '#0f141b', padding: 12, gap: 9, marginBottom: 10 },
  analysisCardCompact: { marginBottom: 0 },
  analysisTopRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  analysisBadges: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  modelPill: { backgroundColor: '#0c3144', borderRadius: 999, borderWidth: 1, borderColor: '#15506b', paddingHorizontal: 8, paddingVertical: 3 },
  modelPillText: { color: C.primary, fontSize: 11, fontWeight: '700' },
  analysisScore: { color: C.text, fontWeight: '800' },
  analysisMeta: { color: C.muted, fontSize: 12 },
  analysisActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  outputButton: { minHeight: 36, borderRadius: 8, borderWidth: 1, borderColor: '#15506B', backgroundColor: '#0f2f3e', paddingHorizontal: 12, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 4 },
  outputButtonText: { color: C.primary, fontWeight: '800', fontSize: 13 },
  deleteButton: { width: 38, minHeight: 38, borderRadius: 8, borderWidth: 1, borderColor: '#69343c', backgroundColor: '#2a171d', alignItems: 'center', justifyContent: 'center' },
  settingLabel: { color: C.muted, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8 },
  settingNote: { color: C.muted, fontSize: 12, lineHeight: 17 },
  checkRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: '#0f141b' },
  checkRowActive: { borderColor: C.primary, backgroundColor: '#0d2530' },
  checkbox: { width: 20, height: 20, borderRadius: 5, borderWidth: 1.5, borderColor: '#455264', backgroundColor: '#0b1017', alignItems: 'center', justifyContent: 'center', marginTop: 1 },
  checkboxActive: { borderColor: C.primary, backgroundColor: C.primary },
  checkmark: { color: '#fff', fontSize: 12, fontWeight: '900', lineHeight: 14 },
  checkContent: { flex: 1, gap: 3 },
  checkLabel: { color: C.muted, fontWeight: '700', fontSize: 14 },
  checkLabelActive: { color: C.text },
  checkNote: { color: C.muted, fontSize: 11, lineHeight: 15 },
  multiModelNote: { backgroundColor: '#0a2533', borderRadius: 6, borderWidth: 1, borderColor: '#15506b', padding: 8 },
  multiModelNoteText: { color: C.primary, fontSize: 12 },
  toggleRow: { flexDirection: 'row', gap: 8 },
  toggleBtn: { flex: 1, height: 38, borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: '#0f141b', alignItems: 'center', justifyContent: 'center' },
  toggleBtnActive: { borderColor: C.primary, backgroundColor: '#103140' },
  toggleText: { color: C.muted, fontWeight: '700', fontSize: 13 },
  toggleTextActive: { color: C.primary },
  modalTitle: { color: C.text, fontSize: 20, fontWeight: '800' },
  input: { height: 44, borderRadius: 8, borderWidth: 1, borderColor: C.border, color: C.text, paddingHorizontal: 12 },
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 8 },
  secondaryButton: { height: 42, paddingHorizontal: 16, borderRadius: 8, backgroundColor: '#1F2740', justifyContent: 'center' },
  secondaryText: { color: C.text, fontWeight: '700' },
  primaryButton: { height: 42, paddingHorizontal: 16, borderRadius: 8, backgroundColor: C.button, justifyContent: 'center' },
  primaryText: { color: '#fff', fontWeight: '800' },
});
