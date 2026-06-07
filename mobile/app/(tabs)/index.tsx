import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { API_URL, useAuth } from '@/contexts/auth-context';

type Analysis = {
  risk?: string;
  status?: string;
  total_score?: number;
};

type Athlete = {
  id: string;
  name: string;
  sport?: string;
  team?: string;
  latest_analysis?: Analysis | null;
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

export default function HomeScreen() {
  const { token, logout } = useAuth();
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [name, setName] = useState('');
  const [sport, setSport] = useState('');
  const [team, setTeam] = useState('');

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
      throw new Error(body.detail || 'Could not load athletes');
    }
    setAthletes(await res.json());
  }, [token]);

  useEffect(() => {
    loadAthletes()
      .catch((err) => Alert.alert('Error', err.message))
      .finally(() => setLoading(false));
  }, [loadAthletes]);

  async function refresh() {
    setRefreshing(true);
    await loadAthletes().catch((err) => Alert.alert('Error', err.message));
    setRefreshing(false);
  }

  async function createAthlete() {
    if (!name.trim()) {
      Alert.alert('Missing name', 'Please enter an athlete name.');
      return;
    }

    const res = await fetch(`${API_URL}/athletes`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, sport, team }),
    });

    if (!res.ok) {
      const body = await res.json();
      Alert.alert('Error', body.detail || 'Athlete could not be created');
      return;
    }

    setName('');
    setSport('');
    setTeam('');
    setModalVisible(false);
    await refresh();
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.primary} size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Athlete Dashboard</Text>
          <Text style={styles.subtitle}>{athletes.length} athletes assigned</Text>
        </View>
        <TouchableOpacity style={styles.iconButton} onPress={logout}>
          <Ionicons name="log-out-outline" size={22} color={C.text} />
        </TouchableOpacity>
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
          <View style={styles.row}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{item.name.charAt(0).toUpperCase()}</Text>
            </View>
            <View style={styles.rowCopy}>
              <Text style={styles.rowTitle}>{item.name}</Text>
              <Text style={styles.rowMeta}>{item.sport || '-'} · {item.team || '-'}</Text>
            </View>
            <Text style={styles.pill}>{item.latest_analysis?.risk || 'No data'}</Text>
          </View>
        )}
      />

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
    </View>
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
  container: {
    flex: 1,
    backgroundColor: C.bg,
    padding: 20,
    paddingTop: 62,
  },
  center: {
    flex: 1,
    backgroundColor: C.bg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    color: C.text,
    fontSize: 28,
    fontWeight: '800',
  },
  subtitle: {
    color: C.muted,
    marginTop: 4,
  },
  iconButton: {
    width: 42,
    height: 42,
    borderRadius: 8,
    backgroundColor: '#1F2740',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stats: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginVertical: 22,
  },
  stat: {
    width: '48%',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
    padding: 16,
  },
  red: { borderLeftColor: C.danger, borderLeftWidth: 3 },
  amber: { borderLeftColor: C.amber, borderLeftWidth: 3 },
  green: { borderLeftColor: C.green, borderLeftWidth: 3 },
  statValue: {
    color: C.text,
    fontSize: 28,
    fontWeight: '800',
  },
  statLabel: {
    color: C.muted,
    marginTop: 4,
  },
  addButton: {
    height: 46,
    borderRadius: 8,
    backgroundColor: C.button,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
    marginBottom: 14,
  },
  addButtonText: {
    color: '#fff',
    fontWeight: '800',
  },
  list: {
    gap: 10,
    paddingBottom: 40,
  },
  row: {
    minHeight: 76,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: '#103140',
    borderWidth: 1,
    borderColor: '#15506B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    color: C.primary,
    fontWeight: '800',
  },
  rowCopy: {
    flex: 1,
  },
  rowTitle: {
    color: C.text,
    fontWeight: '800',
  },
  rowMeta: {
    color: C.muted,
    marginTop: 3,
  },
  pill: {
    color: C.muted,
    borderColor: C.border,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
    overflow: 'hidden',
  },
  empty: {
    color: C.muted,
    textAlign: 'center',
    marginTop: 60,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,.55)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  modal: {
    width: '100%',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
    padding: 22,
    gap: 12,
  },
  modalTitle: {
    color: C.text,
    fontSize: 20,
    fontWeight: '800',
  },
  input: {
    height: 44,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.border,
    color: C.text,
    paddingHorizontal: 12,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 8,
  },
  secondaryButton: {
    height: 42,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: '#1F2740',
    justifyContent: 'center',
  },
  secondaryText: {
    color: C.text,
    fontWeight: '700',
  },
  primaryButton: {
    height: 42,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: C.button,
    justifyContent: 'center',
  },
  primaryText: {
    color: '#fff',
    fontWeight: '800',
  },
});
