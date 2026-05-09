import 'package:flutter/material.dart';

/// Pecunator Design System — Centralized color palette.
///
/// All colors used across the desktop shell are defined here.
/// This eliminates hardcoded hex values scattered across widgets
/// and ensures visual consistency.
///
/// Usage:
///   import '../theme/pecunator_colors.dart';
///   color: PColors.bullGreen
abstract final class PColors {
  // ── Semantic Trading Colors ──────────────────────────────────
  /// Buy / Long / Bullish / Healthy
  static const bullGreen = Color(0xFF00E676);

  /// Sell / Short / Bearish / Critical
  static const bearRed = Color(0xFFFF1744);

  /// Warning / Caution / Fuse triggered
  static const warning = Color(0xFFFF9100);

  /// Attention / Pending / Mid-risk
  static const caution = Color(0xFFFFEA00);

  /// Info / Telemetry / Cyan accent
  static const info = Color(0xFF00E5FF);

  /// Blue accent for secondary data
  static const blueAccent = Color(0xFF448AFF);

  // ── Risk Zone Colors ─────────────────────────────────────────
  /// Used for weight gauge and risk indicators
  static Color zoneColor(double pct, {bool fuseTripped = false}) {
    if (fuseTripped) return bearRed;
    if (pct >= 0.80) return bearRed;
    if (pct >= 0.60) return warning;
    if (pct >= 0.40) return caution;
    if (pct >= 0.15) return bullGreen;
    return info;
  }

  /// Side color for BUY/SELL order display
  static Color sideColor(String side) =>
      side == 'BUY' ? bullGreen : bearRed;

  /// Status color for boolean OK/ERR indicators
  static Color statusColor(bool ok) => ok ? bullGreen : bearRed;

  // ── Background Tints ─────────────────────────────────────────
  /// Dark card background
  static const cardBg = Color(0xFF16213E);

  /// Darker panel background
  static const panelBg = Color(0xFF0A1628);

  /// Subtle surface overlay
  static const surfaceOverlay03 = Color(0x08FFFFFF); // 3% white
  static const surfaceOverlay05 = Color(0x0DFFFFFF); // 5% white
  static const surfaceOverlay08 = Color(0x14FFFFFF); // 8% white

  // ── Hub Identity ─────────────────────────────────────────────
  static const dorothyColor = Colors.greenAccent;
  static const elphabaColor = Color(0xFF00E676);
  static const globalColor = Color(0xFF448AFF);
}
