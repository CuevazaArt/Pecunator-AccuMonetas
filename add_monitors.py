import sys

def process(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. State variables
    masha_state = """class _MashaHubPageState extends State<MashaHubPage> {
  final _tagCtrl = TextEditingController(text: 'Masha');"""
    masha_state_rep = """class _MashaHubPageState extends State<MashaHubPage> {
  int? _apiWeightUsed;
  int _apiWeightLimit = 6000;
  final _tagCtrl = TextEditingController(text: 'Masha');"""
    content = content.replace(masha_state, masha_state_rep)

    thus_state = """class _ThusneldaHubPageState extends State<ThusneldaHubPage> {
  final _tagCtrl = TextEditingController(text: 'Thusnelda');"""
    thus_state_rep = """class _ThusneldaHubPageState extends State<ThusneldaHubPage> {
  int? _apiWeightUsed;
  int _apiWeightLimit = 6000;
  final _tagCtrl = TextEditingController(text: 'Thusnelda');"""
    content = content.replace(thus_state, thus_state_rep)

    # 2. _reload
    reload_logic = """
    try {
      final snap = await _api.gatewaySnapshot();
      final uw = snap['used_weight_1m'];
      if (uw is int) _apiWeightUsed = uw;
      else if (uw is num) _apiWeightUsed = uw.toInt();
      else _apiWeightUsed = int.tryParse('$uw');
      final wl = snap['weight_limit_1m'];
      if (wl is int) _apiWeightLimit = wl;
      else if (wl is num) _apiWeightLimit = wl.toInt();
      else _apiWeightLimit = int.tryParse('$wl') ?? 6000;
    } catch (_) {}
"""
    
    masha_reload = """    for (final id in _expandedBots) {
      await _refreshLogs(id);
    }
    if (mounted) setState(() {});
  }"""
    masha_reload_rep = """    for (final id in _expandedBots) {
      await _refreshLogs(id);
    }""" + reload_logic + """    if (mounted) setState(() {});
  }"""
    content = content.replace(masha_reload, masha_reload_rep)
    
    # 3. Helper Color
    helper_method = """  Color _restWeightColor(int? used, int limit) {
    if (used == null || limit <= 0) return Colors.blueAccent;
    final pct = used / limit;
    if (pct >= 0.9) return Colors.redAccent;
    if (pct >= 0.7) return Colors.orangeAccent;
    return Colors.lightGreenAccent;
  }
"""
    masha_helper_search = """  Future<void> _openGuide() async {"""
    content = content.replace(masha_helper_search, helper_method + "\n" + masha_helper_search)

    # 4. UI Block specific for Masha
    ui_block = """            if (_apiWeightUsed != null && _apiWeightLimit > 0)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Tooltip(
                  message: 'Métrica de cabecera Binance (X-MBX-USED-WEIGHT-1M).',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Peso REST (1m): $_apiWeightUsed / $_apiWeightLimit (${((_apiWeightUsed! / (_apiWeightLimit == 0 ? 1 : _apiWeightLimit)) * 100).toStringAsFixed(1)}%)',
                        style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onSurfaceVariant),
                      ),
                      const SizedBox(height: 4),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          minHeight: 6,
                          value: (_apiWeightUsed!.clamp(0, _apiWeightLimit)) / _apiWeightLimit,
                          valueColor: AlwaysStoppedAnimation<Color>(_restWeightColor(_apiWeightUsed, _apiWeightLimit)),
                          backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
"""
    # Masha specific build block
    masha_build = """      appBar: AppBar(
        title: const Text('Masha2.0 Hub'),"""
    
    # Find Masha build block
    idx_masha = content.find(masha_build)
    idx_masha_insert = content.find("if (_error != '-')", idx_masha)
    content = content[:idx_masha_insert] + ui_block + "            " + content[idx_masha_insert:]
    
    thus_build = """      appBar: AppBar(
        title: const Text('Thusnelda Hub'),"""
        
    idx_thus = content.find(thus_build)
    idx_thus_insert = content.find("if (_error != '-')", idx_thus)
    content = content[:idx_thus_insert] + ui_block + "            " + content[idx_thus_insert:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    process(r'c:\Users\lexar\Desktop\Pecunator\desktop_shell\lib\main.dart')
