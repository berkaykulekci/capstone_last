import { Tabs, Redirect } from 'expo-router';
import React from 'react';
import { ActivityIndicator, View, DeviceEventEmitter } from 'react-native';

import { HapticTab } from '@/components/haptic-tab';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuth } from '@/contexts/auth-context';

export default function TabLayout() {
  const colorScheme = useColorScheme();
  const { token, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (!token) {
    return <Redirect href="/login" />;
  }

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: Colors[colorScheme ?? 'light'].tint,
        headerShown: false,
        tabBarButton: HapticTab,
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color }) => <IconSymbol size={28} name="house.fill" color={color} />,
        }}
        listeners={({ navigation }) => {
          let lastTap = 0;
          return {
            tabPress: (e) => {
              const now = Date.now();
              const DOUBLE_PRESS_DELAY = 350;
              if (now - lastTap < DOUBLE_PRESS_DELAY) {
                DeviceEventEmitter.emit('reset-home-screen');
              }
              lastTap = now;
            },
          };
        }}
      />
      <Tabs.Screen
        name="statistics"
        options={{
          title: 'İstatistikler',
          tabBarIcon: ({ color }) => <IconSymbol size={28} name="chart.bar.fill" color={color} />,
        }}
      />
    </Tabs>
  );
}
