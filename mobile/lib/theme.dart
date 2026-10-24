// CareCompass design tokens, copied from web/src/styles.css (:root).
// Neem (deep teal-green) for trust, haldi (turmeric) for the one warm
// highlight, chuna (lime-wash white) for the ground, sindoor red only for
// emergencies. SOS surfaces use one fixed red in both themes.

import 'package:flutter/material.dart';

@immutable
class CC extends ThemeExtension<CC> {
  final Color bg, surface, surface2, surface3;
  final Color ink, ink2, ink3, line;
  final Color brand, brand2, brandInk, brandSoft;
  final Color haldi, haldiInk, haldiSoft;
  final Color sindoor, sindoor2, sindoorSoft;
  final Color ok, sos, focus;
  final List<BoxShadow> shadow, shadowLift;

  const CC({
    required this.bg,
    required this.surface,
    required this.surface2,
    required this.surface3,
    required this.ink,
    required this.ink2,
    required this.ink3,
    required this.line,
    required this.brand,
    required this.brand2,
    required this.brandInk,
    required this.brandSoft,
    required this.haldi,
    required this.haldiInk,
    required this.haldiSoft,
    required this.sindoor,
    required this.sindoor2,
    required this.sindoorSoft,
    required this.ok,
    required this.sos,
    required this.focus,
    required this.shadow,
    required this.shadowLift,
  });

  /// Filled emergency surfaces: the same in both themes so white text reads.
  static const Color sosFixed = Color(0xFFC62A1C);

  /// Takeover background (web .sos).
  static const Color sosScreen = Color(0xFFB3221A);
  static const Color sosDeep = Color(0xFF9E1D12);

  static const light = CC(
    bg: Color(0xFFEEF4F0),
    surface: Color(0xFFFFFFFF),
    surface2: Color(0xFFE4EEE8),
    surface3: Color(0xFFD5E5DC),
    ink: Color(0xFF10302B),
    ink2: Color(0xFF4A6660),
    // Web token is #6F8A84; darkened a step so small grey text passes WCAG AA
    // (4.5:1) on the chuna background and on surface-2.
    ink3: Color(0xFF557069),
    line: Color(0xFFCFDFD7),
    brand: Color(0xFF0D5A50),
    brand2: Color(0xFF0A463E),
    brandInk: Color(0xFFFFFFFF),
    brandSoft: Color(0xFFD7EBE4),
    haldi: Color(0xFFD99A06),
    haldiInk: Color(0xFF2D2100),
    haldiSoft: Color(0xFFFBEFCC),
    sindoor: Color(0xFFC62A1C),
    sindoor2: Color(0xFF9E1D12),
    sindoorSoft: Color(0xFFFDE6E2),
    ok: Color(0xFF1D7A4B),
    sos: sosFixed,
    focus: Color(0xFFE0A10A),
    shadow: [
      BoxShadow(color: Color(0x0F10302B), blurRadius: 2, offset: Offset(0, 1)),
      BoxShadow(color: Color(0x1210302B), blurRadius: 24, offset: Offset(0, 8)),
    ],
    shadowLift: [BoxShadow(color: Color(0x2E10302B), blurRadius: 40, offset: Offset(0, 12))],
  );

  static const dark = CC(
    bg: Color(0xFF0A1D1A),
    surface: Color(0xFF0F2925),
    surface2: Color(0xFF14332E),
    surface3: Color(0xFF1C4039),
    ink: Color(0xFFE3EFEB),
    ink2: Color(0xFFA3BDB6),
    ink3: Color(0xFF7F9C95),
    line: Color(0xFF234640),
    brand: Color(0xFF3CB6A3),
    brand2: Color(0xFF5FCAB9),
    brandInk: Color(0xFF04211D),
    brandSoft: Color(0xFF143C36),
    haldi: Color(0xFFF0B52C),
    haldiInk: Color(0xFF231900),
    haldiSoft: Color(0xFF3A2E0F),
    sindoor: Color(0xFFFF6B58),
    sindoor2: Color(0xFFFF8A7A),
    sindoorSoft: Color(0xFF3D1611),
    ok: Color(0xFF6CCF98),
    sos: sosFixed,
    focus: Color(0xFFF0B52C),
    shadow: [
      BoxShadow(color: Color(0x4D000000), blurRadius: 2, offset: Offset(0, 1)),
      BoxShadow(color: Color(0x40000000), blurRadius: 24, offset: Offset(0, 8)),
    ],
    shadowLift: [BoxShadow(color: Color(0x80000000), blurRadius: 40, offset: Offset(0, 12))],
  );

  static CC of(BuildContext context) => Theme.of(context).extension<CC>()!;

  @override
  CC copyWith() => this;

  @override
  CC lerp(ThemeExtension<CC>? other, double t) {
    if (other is! CC) return this;
    Color c(Color a, Color b) => Color.lerp(a, b, t)!;
    return CC(
      bg: c(bg, other.bg),
      surface: c(surface, other.surface),
      surface2: c(surface2, other.surface2),
      surface3: c(surface3, other.surface3),
      ink: c(ink, other.ink),
      ink2: c(ink2, other.ink2),
      ink3: c(ink3, other.ink3),
      line: c(line, other.line),
      brand: c(brand, other.brand),
      brand2: c(brand2, other.brand2),
      brandInk: c(brandInk, other.brandInk),
      brandSoft: c(brandSoft, other.brandSoft),
      haldi: c(haldi, other.haldi),
      haldiInk: c(haldiInk, other.haldiInk),
      haldiSoft: c(haldiSoft, other.haldiSoft),
      sindoor: c(sindoor, other.sindoor),
      sindoor2: c(sindoor2, other.sindoor2),
      sindoorSoft: c(sindoorSoft, other.sindoorSoft),
      ok: c(ok, other.ok),
      sos: c(sos, other.sos),
      focus: c(focus, other.focus),
      shadow: t < 0.5 ? shadow : other.shadow,
      shadowLift: t < 0.5 ? shadowLift : other.shadowLift,
    );
  }
}

// Radii (web --r-*)
const double rXl = 28, rLg = 20, rMd = 14, rSm = 10;

// Font families. Latin text uses Anek Latin / Noto Sans; Devanagari glyphs
// fall back to Anek Devanagari / Noto Sans Devanagari (bundled), so mixed
// Hinglish + Hindi text renders in the brand faces.
const String fDisplay = 'AnekLatin';
const List<String> fDisplayFallback = ['AnekDevanagari', 'NotoSansDevanagari'];
const String fBody = 'NotoSans';
const List<String> fBodyFallback = ['NotoSansDevanagari'];

/// Display (headline) text style: Anek, heavy, slightly tight.
TextStyle display(double size, {FontWeight weight = FontWeight.w800, Color? color, double height = 1.15}) => TextStyle(
  fontFamily: fDisplay,
  fontFamilyFallback: fDisplayFallback,
  fontSize: size,
  fontWeight: weight,
  color: color,
  height: height,
  letterSpacing: -0.2,
);

/// Devanagari needs taller lines than Latin (matras above, conjuncts below);
/// give headline styles extra leading when [text] contains Devanagari.
TextStyle dv(TextStyle s, String text) {
  if (!RegExp(r'[ऀ-ॿ]').hasMatch(text)) return s;
  final h = s.height ?? 1.2;
  return s.copyWith(height: h < 1.4 ? 1.4 : h, letterSpacing: 0);
}

/// Body text style: Noto Sans.
TextStyle body(double size, {FontWeight weight = FontWeight.w400, Color? color, double height = 1.45}) => TextStyle(
  fontFamily: fBody,
  fontFamilyFallback: fBodyFallback,
  fontSize: size,
  fontWeight: weight,
  color: color,
  height: height,
);

ThemeData buildTheme(Brightness b) {
  final cc = b == Brightness.dark ? CC.dark : CC.light;
  final scheme = ColorScheme(
    brightness: b,
    primary: cc.brand,
    onPrimary: cc.brandInk,
    primaryContainer: cc.brandSoft,
    onPrimaryContainer: cc.brand2,
    secondary: cc.haldi,
    onSecondary: cc.haldiInk,
    secondaryContainer: cc.haldiSoft,
    onSecondaryContainer: cc.ink,
    tertiary: cc.brand2,
    onTertiary: cc.brandInk,
    error: cc.sindoor,
    onError: Colors.white,
    errorContainer: cc.sindoorSoft,
    onErrorContainer: cc.sindoor,
    surface: cc.surface,
    onSurface: cc.ink,
    onSurfaceVariant: cc.ink2,
    surfaceContainerLowest: cc.surface,
    surfaceContainerLow: cc.bg,
    surfaceContainer: cc.surface2,
    surfaceContainerHigh: cc.surface2,
    surfaceContainerHighest: cc.surface3,
    outline: cc.line,
    outlineVariant: cc.line,
    shadow: Colors.black,
    inverseSurface: cc.ink,
    onInverseSurface: cc.bg,
  );

  final baseText = ThemeData(brightness: b).textTheme.apply(fontFamily: fBody, bodyColor: cc.ink, displayColor: cc.ink);
  TextStyle? fb(TextStyle? s) => s?.copyWith(fontFamilyFallback: fBodyFallback);
  TextStyle? fd(TextStyle? s) =>
      s?.copyWith(fontFamily: fDisplay, fontFamilyFallback: fDisplayFallback, fontWeight: FontWeight.w800);

  final text = baseText.copyWith(
    displayLarge: fd(baseText.displayLarge),
    displayMedium: fd(baseText.displayMedium),
    displaySmall: fd(baseText.displaySmall),
    headlineLarge: fd(baseText.headlineLarge),
    headlineMedium: fd(baseText.headlineMedium),
    headlineSmall: fd(baseText.headlineSmall),
    titleLarge: fd(baseText.titleLarge),
    titleMedium: fb(baseText.titleMedium),
    titleSmall: fb(baseText.titleSmall),
    bodyLarge: fb(baseText.bodyLarge),
    bodyMedium: fb(baseText.bodyMedium),
    bodySmall: fb(baseText.bodySmall),
    labelLarge: fb(baseText.labelLarge)?.copyWith(fontWeight: FontWeight.w700),
    labelMedium: fb(baseText.labelMedium),
    labelSmall: fb(baseText.labelSmall),
  );

  return ThemeData(
    useMaterial3: true,
    brightness: b,
    colorScheme: scheme,
    scaffoldBackgroundColor: cc.bg,
    canvasColor: cc.bg,
    fontFamily: fBody,
    textTheme: text,
    extensions: [cc],
    splashFactory: InkSparkle.splashFactory,
    dividerTheme: DividerThemeData(color: cc.line, thickness: 1, space: 1),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: cc.ink,
      contentTextStyle: body(15, weight: FontWeight.w600, color: cc.bg),
      shape: const StadiumBorder(),
      elevation: 6,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: cc.surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      dragHandleColor: cc.line,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(rXl))),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: cc.brand,
        foregroundColor: cc.brandInk,
        minimumSize: const Size(64, 52),
        padding: const EdgeInsets.symmetric(horizontal: 22),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(rMd)),
        textStyle: body(16, weight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: cc.ink,
        minimumSize: const Size(64, 52),
        padding: const EdgeInsets.symmetric(horizontal: 22),
        side: BorderSide(color: cc.line, width: 1.5),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(rMd)),
        textStyle: body(16, weight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: cc.ink2,
        minimumSize: const Size(40, 40),
        padding: const EdgeInsets.symmetric(horizontal: 10),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(rMd)),
        textStyle: body(15, weight: FontWeight.w700),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      hintStyle: body(16, color: cc.ink3),
      border: InputBorder.none,
    ),
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: cc.brand,
      selectionColor: cc.brand.withValues(alpha: 0.25),
      selectionHandleColor: cc.brand,
    ),
    pageTransitionsTheme: const PageTransitionsTheme(
      builders: {TargetPlatform.android: FadeForwardsPageTransitionsBuilder()},
    ),
  );
}
