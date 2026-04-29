/// Number formatting utilities.

/// Format a number removing trailing zeros and unnecessary decimal places.
String plainNum(dynamic value, {int maxDecimals = 12}) {
  if (value == null) return '0';
  final raw = value.toString().trim();
  if (raw.isEmpty) return '0';
  final n = num.tryParse(raw);
  if (n == null || n.isNaN || n.isInfinite) return raw;
  if (n == 0) return '0';
  if (n is int) return n.toString();

  var out = n.toStringAsFixed(maxDecimals);
  out = out.replaceFirst(RegExp(r'0+$'), '').replaceFirst(RegExp(r'\.$'), '');
  if (out == '-0') return '0';
  return out;
}
