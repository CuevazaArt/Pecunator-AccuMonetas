import 'package:flutter/material.dart';
import '../api_client.dart';

/// Known sub-account registry (no secrets, display-only).
const _subAccountRegistry = [
  {'account_id': 'bluechip', 'role': 'bot', 'description': 'Louise Hub — active strategy account', 'enabled': true},
  {'account_id': 'reserve', 'role': 'reserve', 'description': 'Emergency reserve', 'enabled': false},
  {'account_id': 'dorothy', 'role': 'legacy', 'description': 'Migrated to Louise Hub', 'enabled': false},
  {'account_id': 'elphaba', 'role': 'legacy', 'description': 'Migrated to Louise Hub', 'enabled': false},
];

/// Opens the credential vault + sub-account registry dialog.
///
/// Manages API keys and displays the sub-account fleet.
/// Extracted from home_shell to keep the shell thin.
void showCredentialManagerDialog({
  required BuildContext context,
  required EngineApi api,
  required String activeCredential,
  required String activeCredentialId,
  required List<Map<String, dynamic>> vaultCredentials,
  required VoidCallback onRefresh,
}) {
  final credKeyCtrl = TextEditingController();
  final credSecretCtrl = TextEditingController();
  final credLabelCtrl = TextEditingController();

  showDialog(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setDialogState) {
        return AlertDialog(
          title: Row(
            children: [
              const Icon(Icons.key, size: 18),
              const SizedBox(width: 8),
              const Text('Credenciales & Sub-Cuentas'),
              const Spacer(),
              Text('Activa: $activeCredential',
                  style: const TextStyle(fontSize: 10, color: Colors.white38)),
            ],
          ),
          content: SizedBox(
            width: 560,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── Section: Vault Credentials ──
                  const Text('VAULT (API Keys)', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 1, color: Colors.white38)),
                  const SizedBox(height: 4),
                  // Add new credential
                  Row(
                    children: [
                      SizedBox(width: 80, child: TextField(
                        controller: credLabelCtrl,
                        style: const TextStyle(fontSize: 11),
                        decoration: const InputDecoration(
                          labelText: 'Label', isDense: true,
                          contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                        ),
                      )),
                      const SizedBox(width: 4),
                      Expanded(child: TextField(
                        controller: credKeyCtrl,
                        style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                        decoration: const InputDecoration(
                          labelText: 'API Key', isDense: true,
                          contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                        ),
                      )),
                      const SizedBox(width: 4),
                      Expanded(child: TextField(
                        controller: credSecretCtrl,
                        obscureText: true,
                        style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                        decoration: const InputDecoration(
                          labelText: 'Secret', isDense: true,
                          contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                        ),
                      )),
                      const SizedBox(width: 4),
                      FilledButton(
                        onPressed: () async {
                          final key = credKeyCtrl.text.trim();
                          final secret = credSecretCtrl.text.trim();
                          if (key.isEmpty || secret.isEmpty) return;
                          try {
                            await api.addVaultCredential(
                              apiKey: key,
                              apiSecret: secret,
                              label: credLabelCtrl.text.trim(),
                            );
                            credKeyCtrl.clear();
                            credSecretCtrl.clear();
                            credLabelCtrl.clear();
                            onRefresh();
                            final vault = await api.vaultCredentials();
                            setDialogState(() {
                              vaultCredentials
                                ..clear()
                                ..addAll((vault['items'] as List?)?.cast<Map<String, dynamic>>() ?? []);
                            });
                          } catch (e) {
                            if (ctx.mounted) {
                              ScaffoldMessenger.of(ctx).showSnackBar(
                                SnackBar(content: Text('$e'), backgroundColor: Colors.redAccent),
                              );
                            }
                          }
                        },
                        child: const Text('Add', style: TextStyle(fontSize: 11)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  // List existing vault credentials
                  if (vaultCredentials.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(8),
                      child: Text('Sin credenciales en vault', style: TextStyle(color: Colors.white24, fontSize: 10)),
                    )
                  else
                    ...(vaultCredentials.map((cred) {
                      final id = '${cred['id'] ?? cred['credential_id'] ?? ''}';
                      final label = '${cred['label'] ?? 'unnamed'}';
                      final pubKeyShort = '${cred['public_key_short'] ?? ''}';
                      final last4 = pubKeyShort.isNotEmpty ? pubKeyShort : '${cred['api_key_last4'] ?? ''}';
                      final isActive = cred['is_active'] == true || id == activeCredentialId;
                      final isEnabled = cred['enabled'] != false;

                      return _CredentialTile(
                        id: id,
                        label: label,
                        keyHint: last4,
                        isActive: isActive,
                        isEnabled: isEnabled,
                        onActivate: isEnabled && !isActive ? () async {
                          try {
                            await api.activateVaultCredential(id);
                            onRefresh();
                            final vault = await api.vaultCredentials();
                            setDialogState(() {
                              vaultCredentials
                                ..clear()
                                ..addAll((vault['items'] as List?)?.cast<Map<String, dynamic>>() ?? []);
                            });
                          } catch (e) {
                            if (ctx.mounted) {
                              ScaffoldMessenger.of(ctx).showSnackBar(
                                SnackBar(content: Text('$e'), backgroundColor: Colors.redAccent),
                              );
                            }
                          }
                        } : null,
                        onToggleEnabled: () async {
                          try {
                            if (isEnabled) {
                              await api.disableVaultCredential(id);
                            } else {
                              await api.enableVaultCredential(id);
                            }
                            onRefresh();
                            final vault = await api.vaultCredentials();
                            setDialogState(() {
                              vaultCredentials
                                ..clear()
                                ..addAll((vault['items'] as List?)?.cast<Map<String, dynamic>>() ?? []);
                            });
                          } catch (e) {
                            if (ctx.mounted) {
                              ScaffoldMessenger.of(ctx).showSnackBar(
                                SnackBar(content: Text('$e'), backgroundColor: Colors.redAccent),
                              );
                            }
                          }
                        },
                        onDelete: () async {
                          await api.deleteVaultCredential(id);
                          onRefresh();
                          final vault = await api.vaultCredentials();
                          setDialogState(() {
                            vaultCredentials
                              ..clear()
                              ..addAll((vault['items'] as List?)?.cast<Map<String, dynamic>>() ?? []);
                          });
                        },
                      );
                    })),

                  const Divider(height: 16),

                  // ── Section: Sub-Account Registry ──
                  const Text('SUB-CUENTAS (Registry)', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 1, color: Colors.white38)),
                  const SizedBox(height: 4),
                  ...(_subAccountRegistry.map((sa) {
                    final enabled = sa['enabled'] == true;
                    final role = '${sa['role'] ?? ''}';
                    final desc = '${sa['description'] ?? ''}';
                    return _SubAccountTile(
                      accountId: '${sa['account_id']}',
                      role: role,
                      description: desc,
                      enabled: enabled,
                    );
                  })),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cerrar'),
            ),
          ],
        );
      },
    ),
  );
}

/// Single vault credential tile with enable/disable toggle, activate, and delete actions.
class _CredentialTile extends StatelessWidget {
  final String id;
  final String label;
  final String keyHint;
  final bool isActive;
  final bool isEnabled;
  final VoidCallback? onActivate;
  final VoidCallback onToggleEnabled;
  final VoidCallback onDelete;

  const _CredentialTile({
    required this.id,
    required this.label,
    required this.keyHint,
    required this.isActive,
    required this.isEnabled,
    required this.onActivate,
    required this.onToggleEnabled,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final Color stateColor = isActive && isEnabled
        ? Colors.greenAccent
        : isEnabled
            ? Colors.amber
            : Colors.grey;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 2),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isEnabled
            ? Colors.white.withValues(alpha: 0.04)
            : Colors.white.withValues(alpha: 0.01),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: stateColor.withValues(alpha: 0.25)),
      ),
      child: Row(
        children: [
          // State indicator dot
          Tooltip(
            message: isActive && isEnabled
                ? 'Activa y en uso'
                : isEnabled
                    ? 'Habilitada (no activa)'
                    : 'Deshabilitada',
            child: Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: stateColor,
                boxShadow: (isActive && isEnabled)
                    ? [BoxShadow(color: stateColor.withValues(alpha: 0.5), blurRadius: 4)]
                    : null,
              ),
            ),
          ),
          const SizedBox(width: 8),

          // Label + key hint
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: isActive ? FontWeight.w700 : FontWeight.normal,
                      color: isEnabled ? Colors.white : Colors.white38,
                    ),
                  ),
                  if (isActive) ...[
                    const SizedBox(width: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                      decoration: BoxDecoration(
                        color: Colors.greenAccent.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(3),
                      ),
                      child: const Text('ACTIVE', style: TextStyle(fontSize: 7, fontWeight: FontWeight.w700, color: Colors.greenAccent)),
                    ),
                  ],
                  if (!isEnabled) ...[
                    const SizedBox(width: 4),
                    const Text('DISABLED', style: TextStyle(fontSize: 7, color: Colors.white24)),
                  ],
                ]),
                Text(
                  keyHint.isEmpty ? 'key not loaded' : keyHint,
                  style: const TextStyle(fontSize: 9, color: Colors.white38, fontFamily: 'monospace'),
                ),
              ],
            ),
          ),

          // Action buttons
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Activate button (only shown if enabled but not active)
              if (onActivate != null)
                Tooltip(
                  message: 'Activar esta credencial',
                  child: IconButton(
                    icon: const Icon(Icons.check_circle_outline, size: 16),
                    color: Colors.greenAccent.withValues(alpha: 0.8),
                    splashRadius: 14,
                    onPressed: onActivate,
                  ),
                ),

              // Enable / Disable toggle
              Tooltip(
                message: isEnabled ? 'Deshabilitar' : 'Habilitar',
                child: IconButton(
                  icon: Icon(
                    isEnabled ? Icons.toggle_on : Icons.toggle_off,
                    size: 20,
                  ),
                  color: isEnabled ? Colors.amber : Colors.grey,
                  splashRadius: 14,
                  onPressed: onToggleEnabled,
                ),
              ),

              // Delete
              Tooltip(
                message: 'Eliminar del vault',
                child: IconButton(
                  icon: const Icon(Icons.delete_outline, size: 16),
                  color: Colors.redAccent.withValues(alpha: 0.7),
                  splashRadius: 14,
                  onPressed: onDelete,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Single sub-account tile — extracted for readability.
class _SubAccountTile extends StatelessWidget {
  final String accountId;
  final String role;
  final String description;
  final bool enabled;

  const _SubAccountTile({
    required this.accountId,
    required this.role,
    required this.description,
    required this.enabled,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 2),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: enabled ? Colors.white.withValues(alpha: 0.04) : Colors.white.withValues(alpha: 0.01),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: enabled ? Colors.greenAccent.withValues(alpha: 0.2) : Colors.grey.withValues(alpha: 0.1)),
      ),
      child: Row(
        children: [
          Tooltip(
            message: enabled ? 'Cuenta activa' : 'Cuenta inactiva',
            child: Container(
              width: 8, height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: enabled ? Colors.greenAccent : Colors.grey.withValues(alpha: 0.3),
                boxShadow: enabled ? [BoxShadow(color: Colors.greenAccent.withValues(alpha: 0.4), blurRadius: 4)] : null,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Text(
                    accountId.toUpperCase(),
                    style: TextStyle(
                      fontSize: 11, fontWeight: FontWeight.w700,
                      color: enabled ? Colors.white : Colors.white38,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                    decoration: BoxDecoration(
                      color: role == 'bot'
                          ? const Color(0xFF00E676).withValues(alpha: 0.1)
                          : role == 'legacy'
                              ? Colors.white.withValues(alpha: 0.05)
                              : Colors.blueAccent.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(3),
                    ),
                    child: Text(
                      role,
                      style: TextStyle(
                        fontSize: 7,
                        fontWeight: FontWeight.w600,
                        color: role == 'bot'
                            ? const Color(0xFF00E676)
                            : role == 'legacy'
                                ? Colors.white24
                                : Colors.blueAccent,
                      ),
                    ),
                  ),
                  if (!enabled) ...[
                    const SizedBox(width: 4),
                    const Text('DISABLED', style: TextStyle(fontSize: 7, color: Colors.white24)),
                  ],
                ]),
                Text(description, style: const TextStyle(fontSize: 9, color: Colors.white38)),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
            decoration: BoxDecoration(
              color: (enabled ? Colors.greenAccent : Colors.grey).withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(3),
            ),
            child: Text(enabled ? 'ACTIVE' : 'IDLE', style: TextStyle(fontSize: 7, fontWeight: FontWeight.w700, color: enabled ? Colors.greenAccent : Colors.grey)),
          ),
        ],
      ),
    );
  }
}
