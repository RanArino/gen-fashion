import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_ja.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('ja')
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'gen-fashion'**
  String get appTitle;

  /// No description provided for @navCloset.
  ///
  /// In en, this message translates to:
  /// **'Closet'**
  String get navCloset;

  /// No description provided for @navCoordinate.
  ///
  /// In en, this message translates to:
  /// **'Coordinate'**
  String get navCoordinate;

  /// No description provided for @navHistory.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get navHistory;

  /// No description provided for @navShared.
  ///
  /// In en, this message translates to:
  /// **'Shared'**
  String get navShared;

  /// No description provided for @sharedClosetAbout.
  ///
  /// In en, this message translates to:
  /// **'About shared closet'**
  String get sharedClosetAbout;

  /// No description provided for @signOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get signOut;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @languageJapanese.
  ///
  /// In en, this message translates to:
  /// **'Japanese'**
  String get languageJapanese;

  /// No description provided for @languageEnglish.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get languageEnglish;

  /// No description provided for @loginEyebrow.
  ///
  /// In en, this message translates to:
  /// **'Personal styling studio'**
  String get loginEyebrow;

  /// No description provided for @loginSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in to manage your closet.'**
  String get loginSubtitle;

  /// No description provided for @signInLocal.
  ///
  /// In en, this message translates to:
  /// **'Sign in locally'**
  String get signInLocal;

  /// No description provided for @signInGoogle.
  ///
  /// In en, this message translates to:
  /// **'Sign in with Google'**
  String get signInGoogle;

  /// No description provided for @signingIn.
  ///
  /// In en, this message translates to:
  /// **'Signing in...'**
  String get signingIn;

  /// No description provided for @signInFailed.
  ///
  /// In en, this message translates to:
  /// **'Sign-in failed: {error}'**
  String signInFailed(Object error);

  /// No description provided for @closetTitle.
  ///
  /// In en, this message translates to:
  /// **'Closet'**
  String get closetTitle;

  /// No description provided for @addItem.
  ///
  /// In en, this message translates to:
  /// **'Add item'**
  String get addItem;

  /// No description provided for @uploading.
  ///
  /// In en, this message translates to:
  /// **'Uploading...'**
  String get uploading;

  /// No description provided for @uploadQueued.
  ///
  /// In en, this message translates to:
  /// **'Upload queued; analyzing...'**
  String get uploadQueued;

  /// No description provided for @closetFull.
  ///
  /// In en, this message translates to:
  /// **'Closet is full (20 items).'**
  String get closetFull;

  /// No description provided for @uploadFailed.
  ///
  /// In en, this message translates to:
  /// **'Upload failed: {error}'**
  String uploadFailed(Object error);

  /// No description provided for @deleteItemQuestion.
  ///
  /// In en, this message translates to:
  /// **'Delete item?'**
  String get deleteItemQuestion;

  /// No description provided for @deleteItemBody.
  ///
  /// In en, this message translates to:
  /// **'This removes the item from your closet.'**
  String get deleteItemBody;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @deleteFailed.
  ///
  /// In en, this message translates to:
  /// **'Delete failed: {error}'**
  String deleteFailed(Object error);

  /// No description provided for @editMetadata.
  ///
  /// In en, this message translates to:
  /// **'Edit item metadata'**
  String get editMetadata;

  /// No description provided for @category.
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get category;

  /// No description provided for @colorsComma.
  ///
  /// In en, this message translates to:
  /// **'Colors (comma separated)'**
  String get colorsComma;

  /// No description provided for @season.
  ///
  /// In en, this message translates to:
  /// **'Season'**
  String get season;

  /// No description provided for @tagsComma.
  ///
  /// In en, this message translates to:
  /// **'Tags (comma separated)'**
  String get tagsComma;

  /// No description provided for @gender.
  ///
  /// In en, this message translates to:
  /// **'Gender'**
  String get gender;

  /// No description provided for @genderCommon.
  ///
  /// In en, this message translates to:
  /// **'Common'**
  String get genderCommon;

  /// No description provided for @genderFemale.
  ///
  /// In en, this message translates to:
  /// **'Female'**
  String get genderFemale;

  /// No description provided for @genderMale.
  ///
  /// In en, this message translates to:
  /// **'Male'**
  String get genderMale;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @updateFailed.
  ///
  /// In en, this message translates to:
  /// **'Update failed: {error}'**
  String updateFailed(Object error);

  /// No description provided for @emptyCloset.
  ///
  /// In en, this message translates to:
  /// **'Add your first item to get started.'**
  String get emptyCloset;

  /// No description provided for @unknown.
  ///
  /// In en, this message translates to:
  /// **'Unknown'**
  String get unknown;

  /// No description provided for @analyzing.
  ///
  /// In en, this message translates to:
  /// **'Analyzing...'**
  String get analyzing;

  /// No description provided for @analysisFailed.
  ///
  /// In en, this message translates to:
  /// **'Analysis failed'**
  String get analysisFailed;

  /// No description provided for @statusProcessing.
  ///
  /// In en, this message translates to:
  /// **'PROCESSING'**
  String get statusProcessing;

  /// No description provided for @statusReady.
  ///
  /// In en, this message translates to:
  /// **'READY'**
  String get statusReady;

  /// No description provided for @statusError.
  ///
  /// In en, this message translates to:
  /// **'ERROR'**
  String get statusError;

  /// No description provided for @statusUnknown.
  ///
  /// In en, this message translates to:
  /// **'UNKNOWN'**
  String get statusUnknown;

  /// No description provided for @deleteTooltip.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get deleteTooltip;

  /// No description provided for @editMetadataTooltip.
  ///
  /// In en, this message translates to:
  /// **'Edit metadata'**
  String get editMetadataTooltip;

  /// No description provided for @coordinationTitle.
  ///
  /// In en, this message translates to:
  /// **'Coordination'**
  String get coordinationTitle;

  /// No description provided for @sourceShared.
  ///
  /// In en, this message translates to:
  /// **'Shared'**
  String get sourceShared;

  /// No description provided for @sourceMine.
  ///
  /// In en, this message translates to:
  /// **'Mine'**
  String get sourceMine;

  /// No description provided for @sharedCloset.
  ///
  /// In en, this message translates to:
  /// **'Shared closet'**
  String get sharedCloset;

  /// No description provided for @occasion.
  ///
  /// In en, this message translates to:
  /// **'Occasion'**
  String get occasion;

  /// No description provided for @style.
  ///
  /// In en, this message translates to:
  /// **'Style'**
  String get style;

  /// No description provided for @colors.
  ///
  /// In en, this message translates to:
  /// **'Colors'**
  String get colors;

  /// No description provided for @selectedGenerationLanguage.
  ///
  /// In en, this message translates to:
  /// **'Generation language: {language}'**
  String selectedGenerationLanguage(Object language);

  /// No description provided for @running.
  ///
  /// In en, this message translates to:
  /// **'Running'**
  String get running;

  /// No description provided for @start.
  ///
  /// In en, this message translates to:
  /// **'Start'**
  String get start;

  /// No description provided for @agentTrace.
  ///
  /// In en, this message translates to:
  /// **'Agent trace'**
  String get agentTrace;

  /// No description provided for @errorWithMessage.
  ///
  /// In en, this message translates to:
  /// **'Error: {error}'**
  String errorWithMessage(Object error);

  /// No description provided for @noSessionEvents.
  ///
  /// In en, this message translates to:
  /// **'No session events yet.'**
  String get noSessionEvents;

  /// No description provided for @chooseItems.
  ///
  /// In en, this message translates to:
  /// **'Choose items'**
  String get chooseItems;

  /// No description provided for @generateSelected.
  ///
  /// In en, this message translates to:
  /// **'Generate selected'**
  String get generateSelected;

  /// No description provided for @recommended.
  ///
  /// In en, this message translates to:
  /// **'Recommended'**
  String get recommended;

  /// No description provided for @item.
  ///
  /// In en, this message translates to:
  /// **'Item'**
  String get item;

  /// No description provided for @result.
  ///
  /// In en, this message translates to:
  /// **'Result'**
  String get result;

  /// No description provided for @coordinatePlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Coordinate image will appear here.'**
  String get coordinatePlaceholder;

  /// No description provided for @traceSearchedCloset.
  ///
  /// In en, this message translates to:
  /// **'{agentName} searched closet - {count} candidates'**
  String traceSearchedCloset(Object agentName, Object count);

  /// No description provided for @traceSearchingCloset.
  ///
  /// In en, this message translates to:
  /// **'{agentName} is searching the closet'**
  String traceSearchingCloset(Object agentName);

  /// No description provided for @traceGeneratedCoordinate.
  ///
  /// In en, this message translates to:
  /// **'{agentName} generated the coordinate'**
  String traceGeneratedCoordinate(Object agentName);

  /// No description provided for @traceGeneratingCoordinate.
  ///
  /// In en, this message translates to:
  /// **'{agentName} is generating the coordinate'**
  String traceGeneratingCoordinate(Object agentName);

  /// No description provided for @historyLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load history: {error}'**
  String historyLoadFailed(Object error);

  /// No description provided for @historyEmpty.
  ///
  /// In en, this message translates to:
  /// **'No completed coordinates yet.'**
  String get historyEmpty;

  /// No description provided for @dateUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Date unavailable'**
  String get dateUnavailable;

  /// No description provided for @myCloset.
  ///
  /// In en, this message translates to:
  /// **'My Closet'**
  String get myCloset;

  /// No description provided for @sharedGalleryError.
  ///
  /// In en, this message translates to:
  /// **'Error: {error}'**
  String sharedGalleryError(Object error);

  /// No description provided for @sharedAttribution.
  ///
  /// In en, this message translates to:
  /// **'Shared closet images use the Clothing Dataset (CC BY-SA 4.0)'**
  String get sharedAttribution;

  /// No description provided for @sharedAboutBody.
  ///
  /// In en, this message translates to:
  /// **'Shared closet lets you try coordination without uploading clothes.'**
  String get sharedAboutBody;

  /// No description provided for @sharedAboutDataset.
  ///
  /// In en, this message translates to:
  /// **'Image material: Clothing Dataset (CC BY-SA 4.0)'**
  String get sharedAboutDataset;

  /// No description provided for @sharedAboutAuthor.
  ///
  /// In en, this message translates to:
  /// **'Author: Alexey Grigorev'**
  String get sharedAboutAuthor;

  /// No description provided for @viewDataset.
  ///
  /// In en, this message translates to:
  /// **'View dataset on Kaggle'**
  String get viewDataset;

  /// No description provided for @close.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'ja'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'ja':
      return AppLocalizationsJa();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
