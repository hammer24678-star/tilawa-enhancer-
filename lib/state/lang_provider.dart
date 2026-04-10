import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Strings — all UI text in Arabic and English
class S {
  final bool ar;
  const S({required this.ar});

  String get appName      => ar ? 'محسِّن التلاوة'             : 'Tilawa Enhancer';
  String get subtitle     => ar ? 'ياسر الدوسري — 1425هـ'     : 'Yasser Al-Dossari · 1425H';

  // Home
  String get pickFile     => ar ? 'اختر الملف الصوتي'          : 'Choose audio file';
  String get chooseEngine => ar ? 'اختر المحرك'                : 'Choose Engine';
  String get process      => ar ? 'معالجة'                      : 'Process';
  String get processing   => ar ? 'جارٍ المعالجة...'           : 'Processing...';
  String get uploading    => ar ? 'جارٍ الرفع...'              : 'Uploading...';
  String get serverOnline => ar ? 'الخادم السحابي يعمل ✓'      : 'Cloud server online ✓';
  String get serverOffline=> ar ? 'الخادم غير متصل'            : 'Server offline';
  String get sizeLimit    => ar ? 'MP3 · WAV · M4A · حتى 300MB': 'MP3 · WAV · M4A · up to 300MB';
  String get chunkedBadge => ar ? 'رفع مجزأ'                   : 'Chunked';
  String get done         => ar ? 'اكتملت ✓'                   : 'Done ✓';
  String get downloading  => ar ? 'جارٍ التحميل...'            : 'Downloading...';
  String get downloadBtn  => ar ? 'تحميل الملف المحسَّن'        : 'Download Enhanced File';
  String get savedTo      => ar ? 'محفوظ في Downloads'         : 'Saved to Downloads';
  String get history      => ar ? 'سجل الملفات'                : 'History';
  String get donation     => ar ? 'صدقة جارية'                 : 'Donate';
  String get donationDesc => ar ? 'ساهم في مشروع تحسين التلاوة': 'Support Tilawa project';

  // Results
  String get excellent    => ar ? 'ممتاز'    : 'Excellent';
  String get great        => ar ? 'رائع'     : 'Great';
  String get good         => ar ? 'جيد جداً' : 'Very Good';

  // Welcome
  String get welcomeStart => ar ? 'ابدأ الآن'  : 'Get Started';
  String get howItWorks   => ar ? 'كيف يعمل؟' : 'How it works';
  String get welcomeDesc  =>
    ar ? 'محسِّن التلاوة يرفع جودة التسجيل الصوتي للقرآن الكريم إلى مستوى تسجيلات الشيخ ياسر الدوسري 1425هـ باستخدام معالجة صوتية متقدمة'
       : 'Tilawa Enhancer elevates Quran recitation audio quality to match Sheikh Yasser Al-Dossari\'s legendary 1425H recordings using advanced audio processing';
  String get step1        => ar ? 'اختر الملف الصوتي'      : 'Choose an audio file';
  String get step2        => ar ? 'اختر المحرك المناسب'    : 'Select the right engine';
  String get step3        => ar ? 'انتظر المعالجة السحابية': 'Wait for cloud processing';
  String get step4        => ar ? 'حمِّل الملف المحسَّن'    : 'Download the enhanced file';

  // Settings
  String get settings     => ar ? 'الإعدادات'       : 'Settings';
  String get language     => ar ? 'اللغة'            : 'Language';
  String get arabic       => ar ? 'العربية'          : 'Arabic';
  String get english      => ar ? 'الإنجليزية'       : 'English';
  String get engineHistory=> ar ? 'تاريخ المحركات'   : 'Engine History';
  String get about        => ar ? 'عن التطبيق'       : 'About';
  String get version      => ar ? 'الإصدار 2.1'      : 'Version 2.1';
  String get target       =>
    ar ? 'الهدف: LUFS=-6.29 · RMS=-10.01 · Crest=10.25 · LRA=4.19'
       : 'Target: LUFS=-6.29 · RMS=-10.01 · Crest=10.25 · LRA=4.19';
}

/// InheritedWidget — wraps entire app, ALL screens auto-rebuild
class LangProvider extends InheritedNotifier<ValueNotifier<bool>> {
  const LangProvider({
    super.key,
    required super.notifier,
    required super.child,
  });

  static ValueNotifier<bool> of(BuildContext context) {
    final result =
        context.dependOnInheritedWidgetOfExactType<LangProvider>();
    assert(result != null, 'No LangProvider found in context');
    return result!.notifier!;
  }

  static S strings(BuildContext context) =>
      S(ar: LangProvider.of(context).value);

  static void toggle(BuildContext context) async {
    final notifier = LangProvider.of(context);
    notifier.value = !notifier.value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('lang_ar', notifier.value);
  }
}
